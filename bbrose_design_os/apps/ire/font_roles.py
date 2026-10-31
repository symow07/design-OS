"""The role-based typeface selection layer — §BH32(e).

The §BH31 report measured that the emitter chose a face at eight points and
that none of the 35 activated brand faces was reachable from any of them. This
module is the ONE place a face is chosen. It sits ABOVE the confirmed-font seam
and feeds it: every candidate passes through the seam's own record builder and
the owner-grant channel, and a face is handed to an emitter ONLY when its
record reads VERIFIED_FOR_PRODUCTION. Nothing renders that the record does not
verify.

Faces available to the layer — the ruling's words: "the 35 activated, the Noto
pair, and Naskh once (c) lands — nothing else." The catalogue is built from
``static/fonts/brand2026/PROVENANCE.json`` (the 35, re-hashed against their
pinned sha256) and the three Noto files under ``static/fonts``. A face whose
bytes moved is not in the catalogue.

Roles and defaults — the §BH31 §4.1/§4.2 tables the owner ACCEPTED AS PROPOSED
at §BH32(a), RE-RANKED at §BH33(1) on the three Arabic rows: Noto Naskh Arabic
is the default for arabic-display, arabic-heading and arabic-body, each chain
Naskh → REFUSAL with a named code, never a Latin-only face. Cairo-Bold cannot
render Arabic on this emitter (36 of the 119 presentation forms the shaping
path emits are missing from its cmap): it left every Arabic chain and keeps
only its Latin display role (a 2A-6E confirmed face at display, from the
catalogue). Any re-ranking is one ruled line per role: edit CHAINS.

Script discipline — a Latin run only ever meets a face carrying the 52 basic
letters; an Arabic run only a face carrying the 36 standard letters; both are
measured from the cmap when the catalogue is built, not assumed.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path

from apps.ire.text_script import ARABIC, LATIN, scripts_in

# ---------------------------------------------------------------- roles ------
ROLES = ("display", "heading", "body", "caption", "script-accent",
         "arabic-display", "arabic-heading", "arabic-body")
#: the Design Graph's existing vocabulary, kept as aliases (§BH32(a)):
#: ``regular`` → body, ``bold`` → display (product-name runs).
ALIASES = {"regular": "body", "bold": "display",
           # §BH48(a): the dropper front names its product-name runs `serif-bold`
           # (compose_dropper.py). Before the lift the legacy path drew that key in
           # NotoSans-Regular; the theme path found no face for it and skipped the
           # chunk (recorded under refused.chunks). The layer reads it as display.
           "serif-bold": "display",
           # §BH67(c)5: the product name where the CONCEPT names its face — the display role, led by the concept's own
           # face when it sits in the granted set (CONCEPT_TYPEFACE_KEY); with no lead it resolves exactly as display
           "concept-name": "display"}
#: §BH67(c)5, OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "where the concept names a face that sits
#: inside my granted set — the 35 plus the Noto trio — the concept's face leads. Outside that set, the role layer
#: decides. No face outside the set is ever drawn." The composer marks the name runs CONCEPT_NAME and writes the lead
#: (a catalogue stem, from ``concept_typeface.read``) under CONCEPT_TYPEFACE_KEY in the document's metadata; the layer
#: verifies it through the seam like any candidate (``resolve_role_with``) and, should it not verify, the display chain
#: decides and the record says which was tried. Only the runs so marked are led — the sheet's own furniture, which
#: also prints at display, keeps the chain's face.
CONCEPT_NAME = "concept-name"
CONCEPT_TYPEFACE_KEY = "concept_typeface"
#: aliases whose face is their OWN, resolved per document — every other alias is its target role's face
LEAD_ALIASES = frozenset({CONCEPT_NAME})
#: [His goal after the pitch page, 2026-10-15 (OWNER_BLOCKER_CLEARANCE.md), A (1): "Classify the concept's lettering ...
#: and set each line in the closest granted face with the same weight, spacing, size and colour."] a line of type set in
#: the granted face closest to its concept's lettering (``ire.lettering_faces``) names that face and its weight in its
#: own font: ``line-face:<catalogue stem>@<wght>``. It is a lead as the concept's name is — its face its own, verified
#: through the seam like every candidate, a variable face drawn at exactly that weight (``instance_at``) — and where
#: it does not verify the line prints in the display chain's face, never dropped.
LINE_FACE_PREFIX = "line-face:"


def line_face_key(stem: str, weight: float) -> str:
    """The font a line set in ``stem`` at ``weight`` names (``LINE_FACE_PREFIX``)."""
    return "%s%s@%g" % (LINE_FACE_PREFIX, stem, float(weight))


def parse_line_face(role: str | None) -> tuple[str, float] | None:
    """``(stem, weight)`` of a ``line-face:`` font, or None for any other role."""
    if not role or not role.startswith(LINE_FACE_PREFIX) or "@" not in role:
        return None
    stem, _, weight = role[len(LINE_FACE_PREFIX):].rpartition("@")
    try:
        return stem, float(weight)
    except ValueError:
        return None


def line_face_scripts(role: str | None) -> tuple[bool, bool]:
    """``(latin, arabic)`` of the face a ``line-face:`` font names, from the catalogue; ``(False, False)`` otherwise."""
    parsed = parse_line_face(role)
    if parsed is None:
        return False, False
    entry = catalogue().get(parsed[0]) or derived_entry(parsed[0]) or {}          # [Day 9] a derived face's own scripts
    return bool(entry.get("latin")), bool(entry.get("arabic"))


def is_lead(role: str | None) -> bool:
    """Whether a run's font is a lead — its face its own (the concept's name, or a line's own face)."""
    return bool(role) and (role in LEAD_ALIASES or parse_line_face(role) is not None)
ARABIC_ROLE_FOR = {"display": "arabic-display", "heading": "arabic-heading",
                   "body": "arabic-body", "caption": "arabic-body",
                   "script-accent": "arabic-display"}
#: the named refusal — a run whose chain is exhausted is NOT drawn
REFUSAL_CODE = "FONT_ROLE_UNRESOLVED_NO_VERIFIED_FACE"
CATALOGUE_CODE = "FONT_FACE_OUTSIDE_THE_LAYER_CATALOGUE"

#: §BH33(2): a variable face NEVER renders its default instance. The instance
#: is pinned PER ROLE — Montserrat[wght] heading = wght 700 (Bold), body =
#: wght 400 (Regular), matching the Bold and Regular/Light the §BH28 designs
#: used — and every other variable face in the 35 gets the same rule (five are
#: variable, measured from their fvar tables, not assumed). A role with no
#: pinned weight never receives a variable face: the candidate is skipped on
#: the record with the verdict below and the chain continues.
#:
#: §BH68(c), OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "THE DISPLAY ROLE TAKES THE HEADING PIN — weight
#: 700 for a variable face — unless the face declares its own display instance. Playfair Display and Quicksand draw when
#: a concept names them." So display pins 700. The display CHAIN holds static faces only, so no theme and no default
#: render moves: the pin is reached only by a variable face a concept names for its product name (§BH67(c)5's lead). A
#: face that DECLARES its own display instance — a named instance of its fvar whose style name says Display, read from
#: the file (``display_instance``) — draws at that instance instead (``pinned_weight``). None of the five granted
#: variable faces declares one.
INSTANCE_WEIGHT_BY_ROLE = {"heading": 700.0, "body": 400.0, "display": 700.0}
UNPINNED_VERDICT = "VARIABLE_INSTANCE_UNPINNED"

#: candidate chains per role, catalogue keys = file stems. First candidate =
#: the ruled default; every Latin chain ends at the Noto pair; each Arabic
#: chain is Naskh → REFUSAL (§BH33(1); the pair carries no Arabic letter).
CHAINS = {
    "display":        ("Poppins-Light", "Poppins-Regular", "NotoSans-Bold"),
    "heading":        ("Montserrat[wght]", "Poppins-Bold", "NotoSans-Bold"),
    "body":           ("Poppins-Regular", "NotoSans-Regular"),
    "caption":        ("Poppins-Light", "Poppins-Regular", "NotoSans-Regular"),
    "script-accent":  ("GreatVibes-Regular", "Poppins-Light", "Poppins-Regular", "NotoSans-Bold"),
    "arabic-display": ("NotoNaskhArabic-Regular",),
    # [his goal of 2026-10-06, item 6: "Approve Noto Naskh Arabic Bold ... for Arabic headings"] the granted Bold first
    "arabic-heading": ("NotoNaskhArabic-Bold", "NotoNaskhArabic-Regular"),
    "arabic-body":    ("NotoNaskhArabic-Regular",),
}
SCRIPT_OF_ROLE = {r: (ARABIC if r.startswith("arabic-") else LATIN) for r in ROLES}

#: §BH32(h)(1) EXEMPTION LIST — path-literal, one surface per line, in the layer's
#: own config, reversible only by ruling. A surface named here carries owner-ruled
#: typography evidence (§AB2 / §AC1 / the ledger and packer numbers, the Phase 2A-7
#: golden path, the regulatory sticker) and resolves EXACTLY as at HEAD 41604ac —
#: the Noto pair, Noto Naskh Arabic, the 2A-6E confirmed concept face — until the
#: owner re-rules it. Named by the emitter entry point each surface's evidence was
#: measured through, never by test file.
#: §BH48(a) — LIFTED by the owner's word (2026-09-12): the three container composers on the product
#: path — compose_dropper.py::compose_dropper_sheet, back_panel.py::compose_back_panel and
#: compose_container.py::compose_container_graph — are no longer named here and resolve through the
#: theme, faces and colours; the seven surfaces below are not product composers and stay exempt.
#: Every typography pin the theme faces moved was re-measured under §BH48(a) and re-pinned, listed
#: in that commit; the owner may veto any single re-pin by one line.
#: [the owner's message of 2026-10-29, "Re-pin the four checks per PLAN.md" — CURRENT_DECISIONS.md, "Owner: quality, not
#: count"] the list follows the files it names, nothing else changes: the production PDF's two resolvers moved, whole,
#: into the one die writer (daa57b6), so their entries carry its path; the dieline previews' entry
#: (design_preview.py::export_design_preview_ai) left with its file to archive/ (16ddcf2) — nothing stamps that tag now.
#: Seven entries → six; every surface still exempt resolves exactly as before.
EXEMPT_SURFACES = (
    "apps/ire/compose_vector_art.py::compose_vector_art_graph",  # Phase 2A-7 confirmed-concept golden path — concept-only
    "apps/dielines/exporters/counter_display_files.py::_resolve_fonts",   # the regulatory sticker / production PDF — the Noto trio
    "apps/dielines/exporters/counter_display_files.py::_resolve_arabic_font",
    "apps/dielines/exporters/info_panel.py::draw_info_panel",            # the sticker
    "apps/dielines/exporters/info_panel.py::svg_info_panel",             # the sticker's SVG twin
    "apps/ire/handoff/graph_schema.py::serialize_handoff_graph",         # the 2A handoff — the concept face's name
)
#: the document tag a composer's entry point stamps (``Document.metadata``)
SURFACE_KEY = "typography_surface"
#: §BH32(h)(7): the goal's exercise documents — non-exempt by the owner's word
NON_EXEMPT_EXERCISE = "bh32/goal-exercise"
#: §BH32(h)(3): a candidate the chain skipped, carried in the record at its honest state
SKIPPED_CODE = "FONT_CHAIN_CANDIDATE_SKIPPED"

_STATIC = Path(__file__).resolve().parents[2] / "static" / "fonts"
_BRAND = _STATIC / "brand2026"
_NOTO = ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf", "NotoNaskhArabic-Regular.ttf",
         "NotoNaskhArabic-Bold.ttf")                # [his goal of 2026-10-06, item 6] its Bold, granted

_LATIN_LETTERS = set(range(0x41, 0x5B)) | set(range(0x61, 0x7B))
_ARABIC_LETTERS = set(range(0x0621, 0x063B)) | set(range(0x0641, 0x064B))
#: §BH33(3): the harakat and tanween the non-exempt shaping path keeps
#: (fathatan … sukun, superscript alef) — capability needs their glyphs too
_ARABIC_MARKS = frozenset(range(0x064B, 0x0653)) | {0x0670}
_ARABIC_FORMS: set[int] | None = None


def _arabic_forms_the_emitter_emits() -> set[int]:
    """The presentation-form codepoints the emitter's shaping path (the sticker's
    ``shape_ar``: arabic_reshaper, then bidi) actually emits for the 36 standard
    letters in every joining position. reportlab does NO OpenType shaping: it
    looks these codepoints up in the face's cmap, and a form the face lacks is
    a letter that silently does not render — measured on the §BH32 goal
    documents, where Cairo-Bold dropped the non-joining letters of رحيق الورد.
    A face is Arabic-capable only if it carries every form this path emits."""
    global _ARABIC_FORMS
    if _ARABIC_FORMS is None:
        forms: set[int] = set()
        try:
            from apps.dielines.exporters.text_intl import _libs
            libs = _libs()
        except Exception:  # noqa: BLE001
            libs = None
        if libs is None:
            _ARABIC_FORMS = set()
            return _ARABIC_FORMS
        reshape, _display = libs
        letters = [chr(c) for c in sorted(_ARABIC_LETTERS)]
        for x in letters:
            for probe in (x, x + "\u0628", "\u0628" + x + "\u0628", "\u0628" + x):
                for ch in reshape(probe):
                    if 0x0600 <= ord(ch) <= 0x06FF or 0xFB50 <= ord(ch) <= 0xFEFF:
                        forms.add(ord(ch))
        _ARABIC_FORMS = forms
    return _ARABIC_FORMS

_lock = threading.RLock()     # re-entrant: theme_faces() resolves while holding it and the catalogue takes it again
_catalogue: dict | None = None
_theme: dict | None = None


# ------------------------------------------------------------ catalogue ------
def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inspect(path: Path) -> dict:
    """PostScript name, variable default instance and cmap script capability,
    read from the file with fontTools (never from its name)."""
    from fontTools.ttLib import TTFont
    with TTFont(str(path), lazy=True) as font:
        name = font["name"]
        ps = name.getDebugName(6) or path.stem
        instance, axes = None, {}
        if "fvar" in font:
            instance = name.getDebugName(17) or name.getDebugName(2) or ""
            axes = {a.axisTag: (float(a.minValue), float(a.defaultValue), float(a.maxValue))
                    for a in font["fvar"].axes}
        cmap = set((font.getBestCmap() or {}).keys())
        family = name.getDebugName(16) or name.getDebugName(1) or path.stem
        display_instance = _declared_display_instance(font, name)
    forms = _arabic_forms_the_emitter_emits()
    missing_forms = sorted(forms - cmap) if forms else []
    missing_marks = sorted(_ARABIC_MARKS - cmap)
    return {
        "postscript": ps,
        "family": family,
        "variable_default_instance": instance,
        "variable": bool(axes),
        "axes": axes,
        "display_instance": display_instance,                        # §BH68(c)
        "latin": _LATIN_LETTERS <= cmap,
        # base letters alone are NOT capability on this emitter — the forms are
        "arabic_letters": _ARABIC_LETTERS <= cmap,
        "arabic_forms_missing": len(missing_forms),
        "arabic_marks_missing": len(missing_marks),                 # §BH33(3)
        "arabic": (_ARABIC_LETTERS <= cmap) and bool(forms) and not missing_forms and not missing_marks,
    }


def _declared_display_instance(font, name) -> dict | None:
    """§BH68(c): the face's OWN display instance — a named instance in its fvar whose STYLE name says Display — as
    ``{"name", "wght"}``, or None. Read from the file, never from the family name: "Playfair Display" is a family, and
    its named instances run Regular to Black."""
    if "fvar" not in font:
        return None
    for inst in font["fvar"].instances:
        style = name.getDebugName(inst.subfamilyNameID)
        if style is not None and "display" in style.lower() and "wght" in inst.coordinates:
            return {"name": style, "wght": float(inst.coordinates["wght"])}
    return None


def _physical(path) -> Path:
    """A face path recorded before the Day 6 library migration (materials/...) resolves to the file's new place;
    the recorded path stays the record's identity and the resolver refuses a digest that disagrees."""
    from apps.ire.materials_paths import resolve_material_file, MaterialPathError
    try:
        return resolve_material_file(path)
    except MaterialPathError:
        return Path(path)


def _build_catalogue() -> dict:
    """``{stem: {path, sha256, postscript, latin, arabic, ...}}`` — the 35 (bytes
    re-hashed against PROVENANCE.json), the Noto pair, Naskh and — his goal of 2026-10-06, item 6 — its
    granted Bold; and, D-D7-1 (2026-10-19), the GRANTED pool of the materials library. Nothing else."""
    cat: dict = {}
    prov_path = _BRAND / "PROVENANCE.json"
    if prov_path.exists():
        prov = json.loads(prov_path.read_text())
        for folder, entry in (prov.get("families") or {}).items():
            for f in entry.get("files") or []:
                fname = f.get("file") or ""
                if not fname.lower().endswith((".ttf", ".otf")):
                    continue
                p = _BRAND / folder / fname
                if not p.exists():
                    continue
                sha = _sha256(p)
                if sha != f.get("sha256"):
                    continue                      # bytes moved: not available
                cat[p.stem] = {"path": str(p), "sha256": sha, "origin": f.get("origin", ""),
                               **_inspect(p)}
                if cat[p.stem]["variable"]:
                    # [Day 8 §1a] its static instances under var/fonts/instanced (font_instances), where made
                    from apps.ire import font_instances
                    cat[p.stem]["instances"] = font_instances.instances_of(p.stem, sha)
    for fname in _NOTO:
        p = _STATIC / fname
        if p.exists():
            cat[p.stem] = {"path": str(p), "sha256": _sha256(p), "origin": "STATIC_FONTS",
                           **_inspect(p)}
    # [D-D7-1, 2026-10-19] the GRANTED pool of the materials library, from its catalogue record (font_pool: each file
    # resolved through the migration manifest, digest checked against the census, inspected by _inspect when the record
    # was built). Listed here when its file is present; its BYTES are verified at use, as every candidate's are — the
    # seam re-hashes the file (extract_identity) and the Day 7 grant names the census digest — so a changed file never
    # verifies. A file already in the brand catalogue (nine) keeps its brand entry.
    from apps.ire import font_pool
    root = Path(__file__).resolve().parents[3]
    for entry in font_pool.catalogue_entries():
        if entry.get("already_in_brand_catalogue") or entry["catalogue_stem"] in cat:
            continue
        p = root / entry["path"]
        if not p.exists():
            continue
        cat[entry["catalogue_stem"]] = {"path": str(p), "sha256": entry["sha256"], "origin": font_pool.ORIGIN,
                                        "licence": entry.get("licence"), "family_class": entry.get("family_class"),
                                        **{k: entry[k] for k in ("postscript", "family", "variable_default_instance", "variable", "axes",
                                                                 "display_instance", "latin", "arabic_letters", "arabic_forms_missing",
                                                                 "arabic_marks_missing", "arabic", "instances") if k in entry}}
    # [Day 9, D-D9-5] the faces DERIVED from a granted face under var/fonts/derived (font_instances), where made: a field
    # on the source, as its instances are — never an entry; resolved by their own stem through ``derived_entry``
    from apps.ire import font_instances
    for stem, e in cat.items():
        made = font_instances.derived_of(stem, e["sha256"])
        if made:
            e["derived"] = made
    return cat


def catalogue() -> dict:
    global _catalogue
    with _lock:
        if _catalogue is None:
            _catalogue = _build_catalogue()
        return _catalogue


def reset_cache() -> None:
    """Tests only: forget the catalogue and the theme resolution."""
    global _catalogue, _theme
    with _lock:
        _catalogue, _theme = None, None
        _derived_scripts.clear()


# ---------------------------------------------------------- derived faces ---
#: [Day 9, D-D9-5] a face DERIVED from a GRANTED one — an Arabic display face made emitter-capable
#: (``apps.ire.arabic_display.derive``: the presentation forms the emitter writes mapped to what the face's own GSUB and
#: GPOS draw for them) — is resolved by its own stem the way a variable face's static instance is drawn: the GRANTED
#: source is the verification subject (its path and digest go through the seam and the owner-grant channel), the derived
#: bytes are what reportlab registers and the artefact embeds, under the derived face's own PostScript name, and the
#: script capability is measured from those derived bytes. It is never a catalogue key: the catalogue holds the granted
#: files (a derived face is a field on its source, ``derived``).
DERIVED_ORIGIN = "DERIVED_D-D9-5"
#: a derived face is made at one weight: a line asking another is refused by name, never drawn at the wrong weight
DERIVED_WEIGHT_VERDICT = "DERIVED_FACE_NOT_MADE_AT_THAT_WEIGHT"
_derived_scripts: dict = {}               # (stem, derived sha256) -> the derived bytes' _inspect


def derived_entry(stem: str) -> dict | None:
    """The derived face ``stem`` (``font_instances.derived_face``: its provenance, its file re-hashed against it) as a
    catalogue-shaped entry: the GRANTED source's ``path``, ``sha256`` and ``postscript`` (the verification subject), the
    scripts and forms measured from the DERIVED bytes, and ``derived`` naming the file drawn. None where no such face is
    made here (``var/`` is git-ignored), its bytes moved, the stem is a catalogue stem, or its source is not the
    catalogue's granted face of the recorded digest."""
    from apps.ire import font_instances
    if not stem or stem in catalogue():
        return None
    rec = font_instances.derived_face(stem)
    if rec is None:
        return None
    src = catalogue().get(rec.get("source_stem"))
    if src is None or src["sha256"] != rec.get("source_sha256"):
        return None
    key = (stem, rec["sha256"])
    with _lock:
        scripts = _derived_scripts.get(key)
    if scripts is None:
        scripts = _inspect(Path(rec["path"]))
        with _lock:
            _derived_scripts[key] = scripts
    return {**scripts, "path": src["path"], "sha256": src["sha256"], "postscript": src["postscript"],
            "origin": DERIVED_ORIGIN, "variable": False, "axes": {}, "display_instance": None,
            "variable_default_instance": None,
            "derived": {"stem": stem, "path": rec["path"], "sha256": rec["sha256"], "postscript": rec["postscript"],
                        "family": rec.get("family") or "", "style": rec.get("style") or "", "wght": rec.get("wght"),
                        "source_stem": rec["source_stem"], "source_axes": dict(rec.get("source_axes") or {})}}


def _is_derived(entry: dict) -> bool:
    """[Day 9] ``entry`` is a derived face's own (``derived_entry``), not its GRANTED source: the source's catalogue entry
    lists the faces derived from it under the same field name, ``derived``, which never makes the source one."""
    return entry.get("origin") == DERIVED_ORIGIN


def derived_instance(stem: str, weight: float | None = None) -> dict | None:
    """The derived face ``stem`` as the record ``instance_at`` returns — what reportlab registers and the artefact
    embeds — listed by ``instances_registered`` (so the usage record names it as made from its GRANTED source). At
    exactly ``weight`` when one is asked: a derived face is made at one weight. None where it is not derived here or was
    derived at another weight."""
    entry = derived_entry(stem)
    if entry is None:
        return None
    d = entry["derived"]
    if weight is not None and (d["wght"] is None or abs(float(weight) - float(d["wght"])) >= 0.5):
        return None
    inst = {"postscript": d["postscript"], "family": d["family"], "style": d["style"], "path": d["path"],
            "sha256": d["sha256"], "axes": dict(d["source_axes"]), "derived_from": d["source_stem"],
            "derived_from_sha256": entry["sha256"], "source_default_instance": entry["postscript"], "premade": True,
            "derived": stem}
    with _lock:
        _instances[inst["postscript"]] = inst
    return dict(inst)


# ------------------------------------------------------------- exemption -----
def surface_of(doc_or_metadata) -> str | None:
    """The surface tag of a document or its metadata, or None (anonymous)."""
    md = doc_or_metadata if isinstance(doc_or_metadata, dict) else getattr(doc_or_metadata, "metadata", None)
    tag = (md or {}).get(SURFACE_KEY)
    return str(tag) if tag else None


def is_exempt(doc_or_metadata) -> bool:
    """§BH32(h): an exempt surface resolves exactly as at 41604ac. A reading
    forced by (h)(2) and recorded for the owner: the ruled surfaces' own
    measurers ask the map with NO document, so an anonymous call or an
    untagged document is exempt too; a surface adopts the theme by declaring
    a tag that is not in EXEMPT_SURFACES."""
    tag = surface_of(doc_or_metadata)
    return tag is None or tag in EXEMPT_SURFACES


# ---------------------------------------------------- 41604ac, verbatim ------
def legacy_metric_faces(doc_metadata: dict | None = None) -> dict:
    """``text_metrics.resolve_metric_faces`` exactly as at HEAD 41604ac."""
    from apps.ire.text_metrics import register_font, registered_font_path
    try:
        from apps.dielines.exporters.counter_display_files import (
            _resolve_arabic_font, _resolve_fonts)
        regular, bold = _resolve_fonts()
        arabic = _resolve_arabic_font() or regular
    except Exception:  # noqa: BLE001
        return {}
    names = {"regular": regular, "bold": bold, "arabic": arabic}
    confirmed = (doc_metadata or {}).get("confirmed_font") or {}
    name = confirmed.get("name")
    if name and register_font(name, confirmed.get("path")):
        names["bold"] = name
    return {role: (n, registered_font_path(n)) for role, n in names.items()}


def legacy_emitter_fonts(doc) -> dict:
    """``pdf_ai.emit_pdf_ai``'s role → face map exactly as at HEAD 41604ac."""
    from apps.dielines.exporters.counter_display_files import (
        _register_ttf, _resolve_arabic_font, _resolve_fonts)
    f_reg, f_bold = _resolve_fonts()
    f_ar = _resolve_arabic_font()
    fonts = {"regular": f_reg, "bold": f_bold, "arabic": f_ar or f_reg}
    confirmed = (doc.metadata or {}).get("confirmed_font") or {}
    font_path = confirmed.get("path")
    font_name = confirmed.get("name")
    if font_name and font_path and os.path.exists(font_path):
        if _register_ttf(font_name, font_path):
            fonts["bold"] = font_name
    # [his goal of 2026-10-10, item 6] a carton front's own three roles (``front_faces``), where its document carries
    # them — every other document, and the sticker's own roles, resolve exactly as before (§BH32(h))
    front = ((doc.metadata or {}).get("front_faces") or {}).get("roles") or {}
    for role, face in sorted(front.items()):
        if face.get("name") and face.get("path") and _physical(face["path"]).exists():
            if _register_ttf(face["name"], str(_physical(face["path"]))):
                fonts[role] = face["name"]
    # [his goal after the pitch page, A (1)] each line's own face, where a line names one (``LINE_FACE_PREFIX``)
    for role, r in sorted(line_faces(doc).items()):
        if not r.get("refused"):
            fonts[role] = r["label"]
    return fonts


def legacy_resolved_faces(doc):
    """``container_font_authority._resolved_faces`` exactly as at HEAD 41604ac
    ((d)(ii): an RTL run adds the ``arabic`` role)."""
    from apps.ire.container_font_authority import _regular_face
    from apps.ire.text_metrics import resolve_metric_faces, resolve_metric_font
    roles, outlined, rtl = set(), False, False
    for node, _ in doc.walk():
        if node.type == "text":
            roles.add(node.font or "regular")
            outlined = outlined or bool(getattr(node, "outline", False))
            rtl = rtl or bool(getattr(node, "rtl", False))
    bold_name, bold_path = resolve_metric_font(doc.metadata)
    reg_name, reg_path = _regular_face()
    faces = []
    if "bold" in roles:
        faces.append(("bold", bold_name, bold_path))
    if roles - {"bold"} or not faces:
        faces.append(("regular", reg_name, reg_path))
    if rtl:
        faces.append(("arabic",) + tuple(resolve_metric_faces(doc.metadata).get("arabic") or (None, None)))
    return faces, outlined


# ----------------------------------------------------------- resolution ------
def base_role(role: str) -> str:
    if parse_line_face(role) is not None:
        return "display"                    # [his goal after the pitch page, A (1)] a line's own face: a lead of display
    return ALIASES.get(role, role)


def roles_for_text(role: str, text: str) -> set[str]:
    """The roles a run needs: its base role for Latin/neutral text, the Arabic
    counterpart for Arabic text, both for a mixed run."""
    base = base_role(role)
    scripts = scripts_in(text)
    out: set[str] = set()
    if ARABIC in scripts:
        out.add(ARABIC_ROLE_FOR.get(base, "arabic-body"))
    if LATIN in scripts or not scripts:
        out.add(base if base in ROLES else "body")
    return out


def roles_for_document(doc) -> set[str]:
    needed: set[str] = set()
    for node, _ in doc.walk():
        if node.type == "text":
            needed |= roles_for_text(node.font or "regular", node.text)
    return needed or {"body"}


def verify_candidate(role: str, stem: str) -> dict | None:
    """One candidate through the seam: the seam's own record builder, then the
    owner-grant channel. Returns the record — the caller reads its verification.
    None when the stem is not in the catalogue or cannot carry the role's script."""
    from apps.ire.container_font_authority import SCHEMA, _face_record
    from apps.ire.container_font_owner_grant import apply_owner_grant
    entry = catalogue().get(stem) or derived_entry(stem)       # [Day 9] a derived face: its GRANTED source verifies
    if not entry or not entry.get(SCRIPT_OF_ROLE[role]):
        return None
    rec = _face_record(role=role, name=entry["postscript"], path=entry["path"], confirmed=None)
    out = apply_owner_grant({"schema_version": SCHEMA, "faces": [rec],
                             "outlined_text_present": False,
                             "all_production_verified": False})
    return out["faces"][0]


def resolve_role(role: str) -> dict:
    """Walk the role's chain; the first candidate whose record verifies wins.
    ``{"role", "stem", "label", "path", "postscript", "sha256", "record",
    "tried"}`` or ``{"role", "refused": True, "code", "tried"}``."""
    from apps.ire.container_font_authority import VERIFIED_FOR_PRODUCTION
    tried = []
    for stem in CHAINS.get(role, ()):
        rec = verify_candidate(role, stem)
        if rec:
            verdict = rec["verification"]
        else:
            entry = catalogue().get(stem)
            if entry is None:
                verdict = "NOT_IN_CATALOGUE"
            elif SCRIPT_OF_ROLE[role] == ARABIC and entry.get("arabic_letters") and entry.get("arabic_forms_missing"):
                # the letters are there but the emitter's shaping path emits forms
                # the face lacks: it would drop letters — never handed an Arabic run
                verdict = f"ARABIC_PRESENTATION_FORMS_MISSING({entry['arabic_forms_missing']})"
            elif SCRIPT_OF_ROLE[role] == ARABIC and entry.get("arabic_letters") and entry.get("arabic_marks_missing"):
                verdict = f"ARABIC_MARKS_MISSING({entry['arabic_marks_missing']})"   # §BH33(3): harakat kept
            else:
                verdict = "WRONG_SCRIPT_CAPABILITY"
        tried.append({"stem": stem, "verification": verdict})
        if rec and rec["verification"] == VERIFIED_FOR_PRODUCTION:
            out = _accept(role, stem, rec, tried)
            if out:
                return out
    return {"role": role, "refused": True, "code": REFUSAL_CODE, "tried": tried}


def _accept(role: str, stem: str, rec: dict, tried: list) -> dict | None:
    """The VERIFIED candidate ``stem`` as ``role``'s face. §BH33(2): a variable
    face is accepted ONLY at its pinned instance — the derived static bytes are
    what reportlab registers and the artefact embeds, under the instance's own
    PostScript name; the granted file stays the record's verification subject.
    None (with the tried verdict set) when the role has no pinned weight or the
    registration fails; the chain continues."""
    from apps.ire.text_metrics import register_font, registered_font_path
    entry = catalogue().get(stem) or derived_entry(stem)
    label, path, inst = entry["postscript"], entry["path"], None
    if entry.get("variable") or _is_derived(entry):
        # [Day 9] a derived face draws its derived bytes, as a variable face draws its pinned instance
        inst = derived_instance(stem) if _is_derived(entry) else instance_for(stem, role)
        if inst is None:
            tried[-1]["verification"] = UNPINNED_VERDICT
            return None
        label, path = inst["postscript"], inst["path"]
        held = registered_font_path(label)
        if held and os.path.realpath(held) != os.path.realpath(path):
            label = f"{label}@{inst['sha256'][:8]}"   # a static face of the same name registered first
    if not register_font(label, path):
        tried[-1]["verification"] = "REGISTRATION_FAILED"
        return None
    return {"role": role, "stem": stem, "label": label, "path": path,
            "granted_path": entry["path"], "postscript": inst["postscript"] if inst else entry["postscript"],
            "sha256": entry["sha256"], "instance": inst,
            "variable_default_instance": entry.get("variable_default_instance"),
            "record": rec, "tried": tried}


# ---------------------------------------------------- variable instances -----
_INSTANCE_DIR = Path(tempfile.gettempdir()) / "bbrose_font_instances"
_instance_cache: dict[str, dict] = {}     # "stem|wght=700" -> instance record
_instances: dict[str, dict] = {}          # instance PostScript name -> instance record


def instance_weight(role: str) -> float | None:
    """The pinned wght for ``role`` (aliases resolve to their base role)."""
    return INSTANCE_WEIGHT_BY_ROLE.get(base_role(role))


def pinned_weight(stem: str, role: str) -> float | None:
    """§BH68(c): the wght the variable face ``stem`` draws at for ``role`` — the face's own declared display instance
    where it declares one and the role is display, else the role's pin; None where the role pins none."""
    entry = catalogue().get(stem)
    if entry is not None and entry["display_instance"] is not None and base_role(role) == "display":
        return entry["display_instance"]["wght"]
    return instance_weight(role)


def instance_for(stem: str, role: str) -> dict | None:
    """§BH33(2): the pinned static instance of the variable catalogue face
    ``stem`` for ``role`` — ``{postscript, family, style, path, sha256, axes,
    derived_from, derived_from_sha256, source_default_instance}`` — derived
    from the GRANTED file at first use (fontTools instancer, the name from
    the font's own STAT / fvar named instance, timestamps untouched so the
    bytes are deterministic), written under the OS temp dir, never into
    static/ and never granted separately. None when ``stem`` is not variable,
    the role has no pinned weight, or the weight lies outside the wght axis."""
    entry = catalogue().get(stem)
    if not entry or not entry.get("variable"):
        return None
    weight = pinned_weight(stem, role)
    axis = (entry.get("axes") or {}).get("wght")
    if weight is None or axis is None or weight < axis[0] or weight > axis[2]:
        return None
    key = f"{stem}|wght={weight:g}"
    with _lock:
        inst = _instance_cache.get(key)
        if inst is None:
            inst = _premade(entry, stem, weight) or _instantiate(entry, stem, weight)
            _instance_cache[key] = inst
            _instances[inst["postscript"]] = inst
    return dict(inst)


def instance_at(stem: str, weight: float) -> dict | None:
    """[His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 6: "FRONT TEXT: "Rose Blossom" in the granted face closest to the concept's soft rounded sans (Quicksand or Montserrat), ONE colour, never two pinks or the heavy house bold; "Hand Cream" in the same family, lighter; Arabic in a matching sans (Tajawal or Cairo), not Naskh. No hard rectangle cut out of the roses behind it; soft breathing room as the concept shows, and the soft oval cartouche behind the BBROSE logo."]
    The static instance of the variable catalogue face ``stem`` at ``weight`` — derived as ``instance_for`` derives a
    role's pin, and cached with it — None where ``stem`` is not variable or the weight lies off its wght axis."""
    entry = catalogue().get(stem)
    if not entry or not entry.get("variable"):
        return None
    axis = (entry.get("axes") or {}).get("wght")
    if axis is None or weight < axis[0] or weight > axis[2]:
        return None
    key = f"{stem}|wght={weight:g}"
    with _lock:
        inst = _instance_cache.get(key)
        if inst is None:
            inst = _premade(entry, stem, weight) or _instantiate(entry, stem, weight)
            _instance_cache[key] = inst
            _instances[inst["postscript"]] = inst
    return dict(inst)


def _premade(entry: dict, stem: str, weight: float) -> dict | None:
    """[Day 8 §1a] the static instance made ahead under var/fonts/instanced (``font_instances.make_instance``: every axis
    pinned, provenance beside it) at exactly ``weight``, every other axis at its default, re-hashed against its
    provenance — the record ``_instantiate`` would return, or None (then the instance is derived as before)."""
    from apps.ire import font_instances
    try:
        r = font_instances.static_at(stem, entry["sha256"], weight)
    except (OSError, ValueError):
        return None
    if r is None:
        return None
    return {"postscript": r["postscript"], "family": r["family"] or entry.get("family", ""), "style": r["style"] or "",
            "path": r["path"], "sha256": r["sha256"], "axes": {"wght": float(weight)},
            "derived_from": stem, "derived_from_sha256": entry["sha256"],
            "source_default_instance": entry.get("postscript", ""), "premade": True}


def _instantiate(entry: dict, stem: str, weight: float) -> dict:
    import io
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    font = TTFont(str(_physical(entry["path"])), recalcTimestamp=False)
    renamed = True
    try:
        static = instancer.instantiateVariableFont(font, {"wght": weight}, updateFontNames=True)
    except ValueError:
        # [Day 8, measured] a weight its STAT table names no axis value for (Cormorant Garamond at 500: "Cannot find
        # Axis Values") cannot be renamed by the instancer; the outlines are derived without the rename and the
        # instance is named here, by its weight, so a static face of the default's name is never claimed
        font = TTFont(str(_physical(entry["path"])), recalcTimestamp=False)
        static = instancer.instantiateVariableFont(font, {"wght": weight}, updateFontNames=False)
        renamed = False
    if not renamed:
        base = (static["name"].getDebugName(16) or static["name"].getDebugName(1) or stem).replace(" ", "")
        new_ps = f"{base}-W{weight:g}"
        for record in static["name"].names:
            if record.nameID in (4, 6):
                record.string = new_ps if record.nameID == 6 else f"{base} W{weight:g}"
    buf = io.BytesIO()
    static.save(buf)
    data = buf.getvalue()
    names = static["name"]
    ps = names.getDebugName(6) or f"{stem}-wght{weight:g}"
    sha = hashlib.sha256(data).hexdigest()
    _INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    path = _INSTANCE_DIR / f"{ps}__{sha[:16]}.ttf"
    path = _physical(path)
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
    return {"postscript": ps, "family": names.getDebugName(16) or names.getDebugName(1) or entry.get("family", ""),
            "style": names.getDebugName(17) or names.getDebugName(2) or "",
            "path": str(path), "sha256": sha, "axes": {"wght": weight},
            "derived_from": stem, "derived_from_sha256": entry["sha256"],
            "source_default_instance": entry.get("postscript", "")}


def instances_registered() -> dict:
    """``{instance PostScript name: instance record}`` for every instance this
    process derived — what the usage counter reconciles an embedded instance
    name against."""
    with _lock:
        return {k: dict(v) for k, v in _instances.items()}


def instance_for_record(doc, record_role: str) -> dict | None:
    """§BH33(2): the pinned instance behind a NON-exempt record row, or None
    (a static face, a refused role, or an exempt document)."""
    if is_exempt(doc):
        return None
    layer_role = record_role_map(doc).get(record_role)
    r = resolve_document(doc)["resolutions"].get(layer_role) or {}
    inst = r.get("instance")
    return dict(inst) if inst else None


def resolve_roles(roles) -> dict:
    """``{"faces": {role: (label, path)}, "resolutions": {role: ...},
    "refusals": {role: {"code", "tried"}}}`` for the given roles."""
    faces, resolutions, refusals = {}, {}, {}
    for role in sorted(set(roles)):
        r = resolve_role(role)
        resolutions[role] = r
        if r.get("refused"):
            refusals[role] = {"code": r["code"], "tried": r["tried"]}
        else:
            faces[role] = (r["label"], r["path"])
    return {"faces": faces, "resolutions": resolutions, "refusals": refusals}


def concept_lead(doc_metadata: dict | None) -> str | None:
    """§BH67(c)5: the catalogue stem the concept names for its product name, or None."""
    lead = ((doc_metadata or {}).get(CONCEPT_TYPEFACE_KEY) or {}).get("stem")
    return lead if lead in catalogue() else None


def _apply_lead(doc_metadata: dict | None, faces: dict, resolutions: dict | None = None) -> None:
    """The concept's face for the CONCEPT_NAME runs, verified through the seam; the display chain when it does not
    verify (``resolve_role_with`` walks on), recorded under CONCEPT_NAME either way."""
    stem = concept_lead(doc_metadata)
    if not stem:
        return
    r = resolve_role_with(stem, "display")
    if resolutions is not None:
        resolutions[CONCEPT_NAME] = r
    if not r.get("refused"):
        faces[CONCEPT_NAME] = (r["label"], r["path"])


def resolve_line_face(stem: str, weight: float) -> dict:
    """[His goal after the pitch page, A (1)] the face a line names (``line_face_key``), verified through the seam like
    every candidate: a static face as it is granted, a variable one at exactly ``weight`` (``instance_at``), registered
    under the name it embeds. ``{"role", "stem", "label", "path", "granted_path", "postscript", "sha256", "instance",
    "weight", "record", "tried"}``, or ``{"role", "refused": True, "code", "tried"}`` where it does not verify."""
    from apps.ire.container_font_authority import VERIFIED_FOR_PRODUCTION
    from apps.ire.text_metrics import register_font, registered_font_path
    role = line_face_key(stem, weight)
    # [Day 8] an Arabic line names its own face too (a direction picks an emitter-capable Arabic face from the type
    # book): a face carrying Arabic and no Latin is verified for the Arabic display role
    # [Day 9, D-D9-5] … or a face DERIVED from a granted one (``derived_entry``): its GRANTED source verifies through the
    # seam, its derived bytes draw at the one weight they were made at
    entry = catalogue().get(stem) or derived_entry(stem) or {}
    rec = verify_candidate("arabic-display" if entry.get("arabic") and not entry.get("latin") else "display", stem)
    tried = [{"stem": stem, "verification": rec["verification"] if rec else "NOT_IN_CATALOGUE"}]
    if not rec or rec["verification"] != VERIFIED_FOR_PRODUCTION:
        return {"role": role, "refused": True, "code": REFUSAL_CODE, "tried": tried}
    label, path, inst = entry["postscript"], entry["path"], None
    if entry.get("variable") or _is_derived(entry):
        inst = derived_instance(stem, weight) if _is_derived(entry) else instance_at(stem, weight)
        if inst is None:
            tried[-1]["verification"] = DERIVED_WEIGHT_VERDICT if _is_derived(entry) else UNPINNED_VERDICT
            return {"role": role, "refused": True, "code": REFUSAL_CODE, "tried": tried}
        label, path = inst["postscript"], inst["path"]
        held = registered_font_path(label)
        if held and os.path.realpath(held) != os.path.realpath(path):
            label = f"{label}@{inst['sha256'][:8]}"   # a static face of the same name registered first
    if not register_font(label, path):
        tried[-1]["verification"] = "REGISTRATION_FAILED"
        return {"role": role, "refused": True, "code": REFUSAL_CODE, "tried": tried}
    return {"role": role, "stem": stem, "label": label, "path": path, "granted_path": entry["path"],
            "postscript": inst["postscript"] if inst else entry["postscript"], "sha256": entry["sha256"],
            "instance": inst, "weight": float(weight), "record": rec, "tried": tried}


def line_faces(doc) -> dict:
    """``{font: resolution}`` for every ``line-face:`` font a run of ``doc`` names (``resolve_line_face``)."""
    out = {}
    for node, _ in doc.walk():
        if node.type == "text" and node.font not in out:
            parsed = parse_line_face(node.font)
            if parsed is not None:
                out[node.font] = resolve_line_face(*parsed)
    return out


def resolve_document(doc) -> dict:
    """The role map for ``doc``: every role its runs need, resolved through the
    chains and the seam, plus the legacy keys the emitters read."""
    out = resolve_roles(roles_for_document(doc))
    out["needed"] = sorted(roles_for_document(doc))
    faces = out["faces"]
    for alias, target in ALIASES.items():
        if target in faces:
            faces[alias] = faces[target]
    _apply_lead(getattr(doc, "metadata", None), faces, out["resolutions"])        # §BH67(c)5
    for role, r in line_faces(doc).items():           # [his goal after the pitch page, A (1)] each line's own face
        out["resolutions"][role] = r
        if not r.get("refused"):
            faces[role] = (r["label"], r["path"])
    if "arabic-body" in faces:
        faces["arabic"] = faces["arabic-body"]
    elif "arabic-display" in faces:
        faces["arabic"] = faces["arabic-display"]
    return out


def theme_faces() -> dict:
    """Document-independent defaults for the emitters that draw without a
    Design Graph (the sticker, the previews, the review pages): the four Latin
    roles + arabic-body, resolved once per process through the seam."""
    global _theme
    with _lock:
        if _theme is None:
            _theme = resolve_roles(("display", "heading", "body", "caption", "arabic-body"))
            faces = _theme["faces"]
            for alias, target in ALIASES.items():
                if target in faces:
                    faces[alias] = faces[target]
            if "arabic-body" in faces:
                faces["arabic"] = faces["arabic-body"]
        return _theme


def legacy_role_map(doc_metadata: dict | None = None) -> dict:
    """``{regular, bold, arabic, + every resolved role: (label, path)}`` — the
    map ``text_metrics.resolve_metric_faces`` hands to the measurers, from the
    SAME resolution the emitter draws with. The 2A-6E ``confirmed_font`` entry
    in the metadata is honoured for the bold/display role ONLY when its bytes
    are in the catalogue — nothing outside the 35 + the Noto trio is available
    to the layer — and is otherwise recorded as refused."""
    theme = theme_faces()
    faces = dict(theme["faces"])
    _apply_lead(doc_metadata, faces)          # §BH67(c)5: the measurers see the face the emitter draws
    confirmed = (doc_metadata or {}).get("confirmed_font") or {}
    name, path = confirmed.get("name"), confirmed.get("path")
    if name and path and os.path.exists(path):
        sha = _sha256(Path(path))
        stem = next((s for s, e in catalogue().items() if e["sha256"] == sha), None)
        if stem:
            r = resolve_role_with(stem, "display")
            if not r.get("refused"):
                faces["display"] = faces["bold"] = (r["label"], r["path"])
    return faces


def resolve_role_with(stem: str, role: str) -> dict:
    """Resolve ``role`` with ``stem`` as the first candidate, then its chain."""
    from apps.ire.container_font_authority import VERIFIED_FOR_PRODUCTION
    rec = verify_candidate(role, stem)
    if rec and rec["verification"] == VERIFIED_FOR_PRODUCTION:
        out = _accept(role, stem, rec, [{"stem": stem, "verification": rec["verification"]}])
        if out:
            return out
    return resolve_role(role)


def skipped_candidates(doc) -> list[dict]:
    """§BH32(h)(3): every candidate a chain SKIPPED as void or unverified before
    the face that rendered — carried at its honest state with a named code, so
    the render may fall back but the record never hides it. Empty for an exempt
    document (41604ac had no chains)."""
    if is_exempt(doc):
        return []
    out = []
    for role, r in resolve_document(doc)["resolutions"].items():
        winner = r.get("stem")
        for tried in r.get("tried", []):
            if tried["stem"] == winner:
                break
            entry = catalogue().get(tried["stem"]) or {}
            out.append({"role": role, "stem": tried["stem"], "postscript": entry.get("postscript", ""),
                        "sha256": entry.get("sha256", ""), "verification": tried["verification"],
                        "skipped_code": SKIPPED_CODE})
    return out


def record_faces(doc) -> tuple[list[tuple[str, str | None, str | None]], bool]:
    """What ``container_font_authority._resolved_faces`` records: ``(role, label,
    path)`` for every role the document needs, under the document's own role
    names (``bold``/``regular`` stay ``bold``/``regular``; Arabic runs add
    ``arabic`` and, at display, ``arabic-display``), plus the outlined flag. A
    refused role is recorded with no file so the record shows the refusal.
    §BH32(h): an exempt / anonymous document records exactly as at 41604ac."""
    if is_exempt(doc):
        return legacy_resolved_faces(doc)
    res = resolve_document(doc)
    outlined = any(getattr(n, "outline", False) for n, _ in doc.walk() if n.type == "text")
    declared = record_role_map(doc)
    order = ["bold", "display", CONCEPT_NAME, "heading", "regular", "body", "caption", "script-accent",
             "arabic-display", "arabic-heading", "arabic-body"]          # §BH33(4)
    faces = []
    for rec_role in sorted(declared, key=lambda k: order.index(k) if k in order else 99):
        layer_role = declared[rec_role]
        # §BH67(c)5: a lead alias's row is ITS face — the concept's, when it verified
        own = is_lead(rec_role) and rec_role in res["faces"]
        label, path = res["faces"].get(rec_role if own else layer_role, (None, None))
        # §BH33(2): the record hashes the GRANTED file — for a variable face the
        # instance the artefact embeds is derived from it and named on the row
        granted = (res["resolutions"].get(rec_role if own else layer_role) or {}).get("granted_path")
        faces.append((rec_role, label, granted or path))
    return faces, outlined


def record_role_map(doc) -> dict[str, str]:
    """``{record role: layer role}`` for a non-exempt document — the record's
    own role names (``bold``/``regular`` stay as declared) mapped to the layer
    roles that resolved them. §BH33(4): Arabic runs add arabic-display,
    arabic-heading and arabic-body as DISTINCT rows, never collapsed, so a
    re-ranking of one role to another face leaves no drawn face off the record."""
    declared: dict[str, str] = {}
    for node, _ in doc.walk():
        if node.type != "text":
            continue
        role = node.font or "regular"
        needed = roles_for_text(role, node.text)
        for r in needed:
            declared[r if r.startswith("arabic-") else (role if role in ALIASES or is_lead(role) else r)] = r
    if not declared:
        declared["regular"] = "body"
    return declared


def theme_family(role: str, default: str = "Helvetica") -> str:
    """The resolved theme face's family name for ``role`` (SVG twins), else
    ``default`` when the role is refused."""
    label_path = theme_faces()["faces"].get(role)
    if not label_path:
        return default
    inst = instances_registered().get(label_path[0].split("@", 1)[0])   # §BH33(2)
    if inst:
        return inst["family"] or default
    for entry in catalogue().values():
        if entry["postscript"] == label_path[0]:
            return entry["family"]
    return default


def theme_postscript(role: str, default: str) -> str:
    """The resolved theme face's PostScript name for ``role``, else ``default``."""
    label_path = theme_faces()["faces"].get(role)
    return label_path[0] if label_path else default


__all__ = ["EXEMPT_SURFACES", "SURFACE_KEY", "NON_EXEMPT_EXERCISE", "SKIPPED_CODE", "surface_of", "is_exempt",
           "legacy_metric_faces", "legacy_emitter_fonts", "legacy_resolved_faces", "skipped_candidates",
           "theme_family", "theme_postscript", "ROLES", "ALIASES", "CHAINS", "REFUSAL_CODE", "CATALOGUE_CODE", "catalogue",
           "reset_cache", "base_role", "roles_for_text", "roles_for_document",
           "verify_candidate", "resolve_role", "resolve_roles", "resolve_document",
           "theme_faces", "legacy_role_map", "resolve_role_with", "record_faces",
           "INSTANCE_WEIGHT_BY_ROLE", "UNPINNED_VERDICT", "instance_weight", "pinned_weight", "instance_for",
           "instances_registered", "instance_for_record", "record_role_map",
           "CONCEPT_NAME", "CONCEPT_TYPEFACE_KEY", "LEAD_ALIASES", "concept_lead",
           "LINE_FACE_PREFIX", "line_face_key", "parse_line_face", "is_lead", "resolve_line_face", "line_faces",
           "DERIVED_ORIGIN", "DERIVED_WEIGHT_VERDICT", "derived_entry", "derived_instance"]
