"""Design Graph → PDF-compatible Adobe Illustrator (.ai) emitter (Phase 1).

The interim, pure-Python backend: every graph node becomes a NATIVE editable
PDF object (paths, rectangles, live text, vector barcodes, editable
axial/radial gradients) that Illustrator opens as selectable, recolorable,
reshapeable artwork — no embedded raster except an explicit Image node.

Trade-off vs the jsx emitter: reportlab writes a flat PDF, so groups carry
their names via optional-content/marked-content but do NOT nest as a true
Illustrator layer hierarchy. Editability is full; named nesting is the jsx
emitter's job. Same Design Graph feeds both.

Coordinate handling: the graph is mm, y-DOWN, origin top-left (dieline
convention). reportlab is points, y-UP. We scale by mm and flip y once, here.
"""
from __future__ import annotations

import os

from reportlab.lib.colors import Color as RLColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfgen.canvas import FILL_EVEN_ODD, FILL_NON_ZERO

from apps.ire import brand_mark as _brand_mark
from apps.ire.brand_string_runtime import refuse_if_provisional
from apps.ire.graph import (
    AssetRef,
    Barcode,
    Document,
    GradientFill,
    Group,
    Image,
    MeshFill,
    Path,
    PatternFill,
    Rect,
    SolidFill,
    StickerBridge,
    TextRun,
)


USAGE_SCHEMA = "container_font_usage/1.0"
#: §BH32(f): the counter and the artefact disagree — a defect, not a rounding
USAGE_DISAGREEMENT_CODE = "FONT_USAGE_ARTEFACT_DISAGREEMENT"
#: §BH32(f): the artefact could not be read back (no PyMuPDF) — unmeasured
USAGE_UNRECONCILED_CODE = "FONT_USAGE_UNRECONCILED"


def emit_pdf_ai(doc: Document, out_path: str, *, usage_out: dict | None = None,
                initial_font_role: str | None = None) -> str:
    """Write ``doc`` as a PDF-compatible .ai at ``out_path``; return the path.

    §BH32(f): when ``usage_out`` is given it is filled with the
    ``container_font_usage/1.0`` record — every face that actually drew, per
    run and per character, reconciled against the fonts embedded in the file
    just written (``font_usage_record``). ``initial_font_role`` optionally starts the canvas in an already-resolved
    document role instead of declaring ReportLab's unused base-14 default (Day 14 construction/print requirement).
    An unresolved role is refused; the historical default stays unchanged when this option is absent.

    Refuses outright, writing nothing, when ``doc`` carries provisional brand
    copy — see ``refuse_if_provisional``. §AW1 put the closure here because this
    is the one function every .ai on every path runs through, and a per-call-site
    list had already been measured incomplete.
    """
    # §AW1 — AHEAD OF EVERY BYTE THIS FUNCTION WRITES, including the font
    # registration below, which mutates a process-global reportlab registry. The
    # import is TOP-LEVEL, not deferred into this body, and that is deliberate:
    # §AV5's third gate carried its gate but not its import, the names resolved
    # at CALL time, "the module imports, the file compiles, and grep confirms
    # the gate sits ahead of the writer" — and it raised `NameError` under a
    # real invocation. A top-level import moves that failure to import time,
    # where it cannot masquerade as a refusal.
    refuse_if_provisional(doc, artefact=os.path.basename(out_path) or out_path)

    # THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803, the block headed "Before I start
    # testing"): "When I approve the logo trace, switch the mark to it so gold foil can print." A mark drawn from the
    # approved vector master reaches this emitter as an AssetRef — the box every instrument reads — and is EXPANDED
    # HERE into the master's own outlines at nonzero winding, BEFORE a byte is drawn and before any plate is
    # collected: `_draw_finish_plates` cuts a node that has no segments as its BOX (`_rect_segments`), which would
    # cut the foil as a rectangle, and `_dispatch_node` draws an unresolved AssetRef as nothing. A mark no master
    # resolves is refused by name (`BRAND_MARK_UNRESOLVED`), never drawn as nothing. A document with no mark is
    # returned as is — the same object — so nothing below moves for it.
    doc = _brand_mark.expand(doc)

    # §BH39(d): the placement seam — a REFERENCE asset can never be placed, a
    # materials/ source without its placement record is refused, and a
    # conditioned PRODUCTION asset whose credit is not visible resolves
    # REFERENCE for THIS output (its Image is skipped, the resolution recorded).
    # Ahead of every byte, like the provisional gate above.
    from apps.ire import materials_placement as _MP
    skip_images, placement_usage = _MP.refuse_or_skip(doc)
    from apps.ire.materials_paths import resolved_document_images
    doc = resolved_document_images(doc, skip=skip_images)

    # §BH32(e): the role-based selection layer chooses EVERY face, through the
    # confirmed-font seam — a role's face is in ``fonts`` only when its record
    # verified; a refused role is absent and its runs are not drawn (W2).
    from apps.ire.font_roles import (is_exempt, legacy_emitter_fonts,
                                     legacy_role_map, resolve_document, theme_faces)
    # §BH32(h): an exempt / anonymous / untagged document resolves EXACTLY as
    # at 41604ac — the Noto pair, Naskh, the 2A-6E confirmed concept face.
    exempt = is_exempt(doc)
    if exempt:
        fonts = legacy_emitter_fonts(doc)
        refusals = {}
    else:
        resolution = resolve_document(doc)
        # the theme's legacy keys (regular/bold/arabic) are always present —
        # the sticker bridge draws with them even when the graph has no such
        # runs — and the document's own resolution overrides them role by role
        fonts = {role: label for role, (label, _p) in theme_faces()["faces"].items()}
        fonts.update({role: label for role, (label, _p) in resolution["faces"].items()})
        # 2A-6E: the task-scoped confirmed concept face for the product-name
        # (bold/display) runs — honoured by the layer ONLY when its bytes are
        # in the catalogue (the 35 + the Noto trio); nothing else is available
        if (doc.metadata or {}).get("confirmed_font"):
            legacy = legacy_role_map(doc.metadata)
            if "bold" in legacy:
                fonts["bold"] = fonts["display"] = legacy["bold"][0]
        refusals = resolution["refusals"]

    page_w_pt, page_h_pt = doc.page_w * mm, doc.page_h * mm
    initial = {}
    if initial_font_role is not None:
        if initial_font_role not in fonts or initial_font_role in refusals:
            raise ValueError('initial font role did not resolve: %s' % initial_font_role)
        initial['initialFontName'] = fonts[initial_font_role]
    c = rl_canvas.Canvas(out_path, pagesize=(page_w_pt, page_h_pt), **initial)
    c.setTitle(doc.title or "BBROSE design")

    def X(x_mm: float) -> float:
        return x_mm * mm

    def Y(y_mm: float) -> float:
        # graph y-down (0 at top) → PDF y-up (0 at bottom)
        return page_h_pt - y_mm * mm

    ctx = _Ctx(c, X, Y, fonts, refusals, exempt=exempt)
    ctx.arabic_marks = bool((doc.metadata or {}).get(ARABIC_MARKS_KEY))   # [his rule 1]
    ctx.logical_text = bool((doc.metadata or {}).get("logical_text/1.0"))
    ctx.skip_images = skip_images   # §BH39(d)
    ctx.colour_doc = None if exempt else doc   # §BH39(e): the layer resolves only a non-exempt document
    layered = bool((doc.metadata or {}).get("layers/1.0"))
    used: set = set()
    _draw_root(doc.root, ctx, layered, used)
    c.showPage()
    if doc.inside is not None:
        # [his final goal, 2026-10-05, B1: "Two artboards, OUTSIDE and INSIDE."] the inside on the second page
        _draw_root(doc.inside, ctx, layered, used)
        c.showPage()
    # §BH65(c)2: every finish's PLATE on its own page after the artwork — none when no node carries a finish, so a
    # document that uses no finish writes exactly the one page it always did
    plates = _draw_finish_plates(ctx)
    c.save()
    if layered:
        # [his final goal, 2026-10-05, B2] the layers named in the file, its guides never printed
        from apps.dielines.exporters import counter_display_files as layers
        layers.apply_layers(out_path, used, pages=[0, 1] if doc.inside is not None else [0])
    if usage_out is not None:
        usage_out.clear()
        usage_out.update(font_usage_record(out_path, ctx))
        from apps.ire.colour_roles import USAGE_SCHEMA as _CU
        # §BH50(f)(7): each row carries the cmyk it draws in (None on an RGB row), so a CMYK application on the
        # page is matched by its components — in the colour space it is DRAWN in, never through an ICC conversion
        _cu = {"schema_version": _CU,
               "rows": [dict({k: v for k, v in r.items() if k != "color"},
                             cmyk=(list(r["color"].cmyk) if getattr(r.get("color"), "cmyk", None) else None))
                        for r in ctx.colour_cache.values()],
               "counter": dict(ctx.colour_usage), "gradient_stops": dict(ctx.colour_stops), "exempt": ctx.exempt}
        from apps.ire.colour_roles import reconcile_colours as _reconcile_colours
        # §BH39(f) as widened by §BH50(f)(7): the counter against EVERY place the artefact applies colour —
        # fills, strokes, text and gradient stops — both ways, or a named defect; never a raise
        _cu["reconciliation"] = _reconcile_colours(out_path, _cu)
        usage_out[_CU] = _cu
        usage_out[_MP.USAGE_SCHEMA] = dict(placement_usage,
                                            reconciliation=_MP.reconcile_images(out_path, placement_usage))   # §BH39(f)
        from apps.ire.container_finishes import SCHEMA as _FP
        usage_out[_FP] = plates                                                                          # §BH65(c)2
    return out_path


def _postscript_of(label: str) -> str:
    """The PostScript name reportlab will embed for a registered label; the
    label itself for a built-in (Helvetica) or an unknown name."""
    try:
        from reportlab.pdfbase import pdfmetrics
        name = getattr(pdfmetrics.getFont(label).face, "name", None)
        if isinstance(name, bytes):                 # a TrueType face holds it as bytes
            name = name.decode("latin-1", "replace")
        return str(name or label)
    except Exception:  # noqa: BLE001
        return label


#: §BH68(c), OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "Playfair Display and Quicksand draw when a
#: concept names them." MuPDF holds a font's name in 32 bytes — the six-letter subset tag, "+", and 24 characters — so a
#: span reports a LONGER PostScript name cut at 24. Playfair Display's 700 instance, "PlayfairDisplayRoman-Bold" (25
#: characters), is the first face the layer hands out whose name is longer, and this reconciliation read its correct
#: PDF as FONT_USAGE_ARTEFACT_DISAGREEMENT: "PlayfairDisplayRoman-Bol" embedded, "PlayfairDisplayRoman-Bold" counted. The
#: page's own font resources carry the whole name (``_declared_faces``). A span name of exactly this length is the
#: declared font whose name it begins, where exactly one does; the rule — every counted face embedded and every
#: embedded face counted — is not touched. §BH58(a): an instrument that refuses what he rules drawn is repaired; the
#: rule it serves is not moved.
_MUPDF_NAME_CHARS = 24


def _whole_names(span_names: set, declared: set) -> set:
    """The span census's names, each cut name read as the declared font it begins (§BH68(c))."""
    out = set()
    for name in span_names:
        whole = ([d for d in declared if d != name and d.startswith(name)]
                 if len(name) == _MUPDF_NAME_CHARS else [])
        out.add(whole[0] if len(whole) == 1 else name)
    return out


def _embedded_faces(path: str) -> set[str] | None:
    """Base names of the fonts that DREW text in the written file — the span
    census read back with PyMuPDF (the instrument the §BH31 report measured
    the owner's files with); None when the instrument is unavailable. A font
    resource the page declares without drawing a glyph (reportlab's default
    Times-Roman) is not a face that rendered; ``_declared_faces`` lists it.
    §BH68(c): a name MuPDF cut is read whole (``_whole_names``)."""
    try:
        import fitz
    except Exception:  # noqa: BLE001
        return None
    names: set[str] = set()
    with fitz.open(path) as pdf:
        for page in pdf:
            for block in page.get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            names.add(str(span.get("font", "")).split("+", 1)[-1])
    return _whole_names(names, _declared_faces(path))


def _declared_faces(path: str) -> set[str]:
    """Font resources the page declares (drawn or not)."""
    try:
        import fitz
    except Exception:  # noqa: BLE001
        return set()
    names: set[str] = set()
    with fitz.open(path) as pdf:
        for page in pdf:
            for entry in page.get_fonts(full=True):
                names.add(str(entry[3]).split("+", 1)[-1])
    return names


def font_usage_record(path: str, ctx: "_Ctx") -> dict:
    """§BH32(f): ``container_font_usage/1.0`` — what drew, reconciled against
    what the artefact carries. ``faces`` lists every face the emitter set with
    its runs and characters, roles and scripts; ``refused`` lists the roles the
    layer refused and the chunks withheld; ``reconciliation`` compares the
    counter's faces to the embedded fonts — every counted face must be embedded
    and every embedded face counted, or the code fires."""
    from apps.ire.font_roles import catalogue, instances_registered
    sha_by_label = {e["postscript"]: e["sha256"] for e in catalogue().values()}
    # §BH33(2): a pinned instance is counted under the name the artefact embeds;
    # its row carries the derived bytes' sha256 and names the granted face
    instances = instances_registered()
    sha_by_label.update({ps: i["sha256"] for ps, i in instances.items()})
    faces = []
    for label, u in sorted(ctx.usage.items()):
        row = {"postscript": label, "sha256": sha_by_label.get(label, ""),
               "runs": u["runs"], "chars": u["chars"],
               "roles": sorted(u["roles"]), "scripts": sorted(u["scripts"]),
               # a face the LAYER did not hand out (a widget drew it) —
               # on the record by name for the owner, never silent
               "outside_layer": label not in sha_by_label}
        if label in instances:
            i = instances[label]
            row["instance_of"] = {"stem": i["derived_from"], "sha256": i["derived_from_sha256"],
                                  "axes": dict(i["axes"]), "source_default_instance": i["source_default_instance"]}
        faces.append(row)
    outside = sorted(f["postscript"] for f in faces if f["outside_layer"])
    embedded = _embedded_faces(path)
    counted = set(ctx.usage)
    declared_only = sorted(_declared_faces(path) - (embedded or set()))
    if embedded is None:
        recon = {"status": "UNRECONCILED", "embedded": [], "counted": sorted(counted),
                 "missing_from_artefact": [], "unaccounted_in_artefact": [],
                 "agree": False, "codes": [USAGE_UNRECONCILED_CODE]}
    else:
        missing = sorted(counted - embedded)
        unaccounted = sorted(embedded - counted)
        agree = not missing and not unaccounted
        recon = {"status": "RECONCILED", "embedded": sorted(embedded), "counted": sorted(counted),
                 "declared_without_glyphs": declared_only,
                 "missing_from_artefact": missing, "unaccounted_in_artefact": unaccounted,
                 "agree": agree, "codes": [] if agree else [USAGE_DISAGREEMENT_CODE]}
    return {"schema_version": USAGE_SCHEMA, "artefact": os.path.basename(path),
            "faces": faces, "outside_layer": outside,
            "refused": {"roles": ctx.refusals, "chunks": list(ctx.skipped)},
            "reconciliation": recon}


#: [his rule 1 for 119 and every design, 2026-10-05: "the Arabic ملمّع as my brief writes it"] a document that declares
#: it keeps its Arabic marks — the harakat, the shadda — has them drawn on the exempt drawer too, which otherwise shapes
#: them away as at 41604ac; a document without it (the sticker family, the pinned surfaces) draws exactly as before
ARABIC_MARKS_KEY = "arabic_marks_kept"


class _Ctx:
    __slots__ = ("c", "X", "Y", "fonts", "refusals", "skipped", "exempt", "arabic_marks", "logical_text", "usage", "skip_images",
                 "colour_doc", "colour_cache", "colour_usage", "colour_stops", "finishes", "clips", "plates",
                 "masks", "layer", "alpha", "own", "frames")

    def __init__(self, c, X, Y, fonts, refusals=None, exempt=False):
        self.layer = None          # [his final goal, B2] the named layer being drawn, on a layered document
        self.c, self.X, self.Y, self.fonts = c, X, Y, fonts
        self.refusals = dict(refusals or {})
        self.skipped = []          # §BH32(e): chunks NOT drawn (role refused)
        self.exempt = bool(exempt)  # §BH32(h): draw exactly as at 41604ac
        self.arabic_marks = False   # [his rule 1, 2026-10-05] the document keeps its Arabic marks (ARABIC_MARKS_KEY)
        self.usage = {}            # §BH32(f): face label -> runs/chars/roles/scripts
        self.skip_images = set()   # §BH39(d): Image nodes resolved REFERENCE for this output
        self.colour_doc = None     # §BH39(e): the document whose role map the layer resolves (None = exempt)
        self.colour_cache = {}     # hex -> resolved row
        self.colour_usage = {}     # drawn hex -> count of colour operators
        self.colour_stops = {}     # §BH50(f)(7): drawn hex -> gradient stops drawn (its own unit; the counter above keeps its own)
        self.finishes = []         # §BH65(c)2: the finishes each enclosing Group put in force, innermost last
        self.clips = []            # §BH65(c)2: the clip paths in force, outermost first — a plate is cut by them too
        # [his goal of 2026-10-13, (2)] the clips and the turns in force, in the order they were entered — a plate cut
        # under a turned group is turned with it, in register
        self.frames = []
        self.plates = {}           # §BH65(c)2: plate name -> {"kind", "items": [(node, clips, region)]}, in draw order
        self.masks = 0             # §BH65(c)6: soft masks written, so each mask form has its own name
        # [his goal of 2026-10-12, (3): "a shape's own fade (e.g. 85%) is right; the drawing must keep it too, so the
        # drawing and the layered file match."] the enclosing groups' opacity, multiplied; and the element being drawn's
        # own, times theirs — every paint's alpha is its own times this, as the layered file's items multiply
        self.alpha = 1.0
        self.own = 1.0

    def count(self, face: str, role: str, script: str, text: str) -> None:
        # the counter records the face's POSTSCRIPT name — what the artefact
        # embeds — not reportlab's registration label ("NotoSans" registers
        # the file whose PostScript name is NotoSans-Regular)
        face = _postscript_of(face)
        u = self.usage.setdefault(face, {"runs": 0, "chars": 0, "roles": set(), "scripts": set()})
        u["runs"] += 1
        u["chars"] += len(text)
        u["roles"].add(role)
        u["scripts"].add(script)


# --- per-node drawing --------------------------------------------------------


#: §BH65(c)5 — the planner's spelling -> the PDF blend mode's own name
_PDF_BLEND = {"multiply": "Multiply", "screen": "Screen", "overlay": "Overlay", "soft-light": "SoftLight",
              "hard-light": "HardLight", "darken": "Darken", "lighten": "Lighten", "color-dodge": "ColorDodge",
              "color-burn": "ColorBurn", "difference": "Difference", "exclusion": "Exclusion"}


def _draw_node(node, ctx: _Ctx) -> None:
    saved = ctx.own
    ctx.own = ctx.alpha                    # [his goal of 2026-10-12, (3)] a shadow fades with its groups, not its node
    try:
        # §BH65(c)7: a soft shadow is drawn BEFORE its node, under it
        if getattr(node, "shadow", None) is not None:
            _draw_soft_shadow(node, ctx)
        if not isinstance(node, Group):
            # [his goal of 2026-10-12, (3)] the element's own fade, times its groups'
            ctx.own = ctx.alpha * float(getattr(node, "opacity", 1.0) if getattr(node, "opacity", None) is not None
                                        else 1.0)
        # §BH65(c)5: a node with a blend mode prints in it, inside its own graphics state so it reaches nothing after
        mode = getattr(node, "blend_mode", None)
        if mode:
            ctx.c.saveState()
            ctx.c.setBlendMode(_PDF_BLEND[mode])
            try:
                _dispatch_node(node, ctx)
            finally:
                ctx.c.restoreState()
            return
        _dispatch_node(node, ctx)
    finally:
        ctx.own = saved


def _alpha(ctx, value: float) -> float:
    """[His goal of 2026-10-12, (3).] A paint's alpha as drawn: its own times the element's and its groups' — on an
    exempt document (§BH32(h)) exactly as before, its own."""
    return value if ctx.exempt else value * ctx.own


def _groups_alpha(ctx, value: float) -> float:
    """A depiction's alpha (a gloss, a relief): its own times the enclosing groups', as the layered file's."""
    return value if ctx.exempt else value * ctx.alpha


def _dispatch_node(node, ctx: _Ctx) -> None:
    # reportlab has no marked-content / layer support, so this flat backend
    # cannot carry object names or a nested hierarchy into the PDF — that is
    # precisely the jsx emitter's job. Here every node is drawn as an
    # editable object; names live on in the Design Graph for the jsx pass.
    if isinstance(node, Group):
        _draw_group(node, ctx)
    elif isinstance(node, Rect):
        _draw_rect(node, ctx)
    elif isinstance(node, Path):
        _draw_path(node, ctx)
    elif isinstance(node, TextRun):
        _draw_text(node, ctx)
    elif isinstance(node, Barcode):
        _draw_barcode(node, ctx)
    elif isinstance(node, Image):
        _draw_image(node, ctx)
    elif isinstance(node, StickerBridge):
        _draw_sticker_bridge(node, ctx)
    elif isinstance(node, AssetRef):
        # Unresolved at emit time = library miss. The resolver should have
        # rewritten it to a Group before now; draw nothing rather than fail.
        # [The owner's second answer of 2026-09-25: a `brand-mark:` AssetRef never
        # reaches this branch — `emit_pdf_ai` expands it into the master's outlines
        # or refuses it by name, because the house mark drawn as nothing is not a
        # library miss.]
        pass


def _pdf_turn(turn, ctx: "_Ctx") -> tuple:
    """[His goal of 2026-10-13, (2).] A group's turn (mm, y down) as the PDF's own matrix (points, y up): the page's
    mapping, the turn, and the mapping back — ``(A, B, C, D, E, F)`` for ``cm``."""
    a, b, c, d, e, f = turn
    tx, ty = ctx.X(0.0), ctx.Y(0.0)
    k = ctx.X(1.0) - tx
    return (a, -b, -c, d, -a * tx + c * ty + k * e + tx, ty + b * tx - d * ty - k * f)


def _draw_group(node: Group, ctx: _Ctx) -> None:
    c = ctx.c
    turned = getattr(node, "turn", None) is not None
    if turned:
        # [his goal of 2026-10-13, (2)] what it holds laid out upright in its own frame, turned onto the page
        c.saveState()
        c.transform(*_pdf_turn(node.turn, ctx))
        ctx.frames.append(("turn", node.turn))
    clipped = node.clip is not None
    masked = node.opacity_mask is not None
    if masked:
        # §BH65(c)6: its own graphics state, so the soft mask reaches nothing after this group
        c.saveState()
        c._code.append("/%s gs" % _soft_mask_state(node.opacity_mask, ctx))
    if clipped or node.opacity < 1.0:
        c.saveState()
    if node.opacity < 1.0:
        c.setFillAlpha(node.opacity)
        c.setStrokeAlpha(node.opacity)
    saved_alpha = ctx.alpha
    if not ctx.exempt:
        ctx.alpha *= node.opacity          # [his goal of 2026-10-12, (3)] what it holds fades with it
    if clipped:
        clip = _segments_to_path(c, node.clip, ctx)
        c.clipPath(clip, stroke=0, fill=0)
        ctx.clips.append(node.clip)
        ctx.frames.append(("clip", node.clip))
    # [D-D9-5, Day 9] a group that names the words it draws (``Group.actual_text``: a logotype drawn as outlines) is
    # wrapped in a marked-content span whose ActualText is those words, so the drawn copy extracts as text — opened
    # inside every state, turn and clip the group pushed and closed before they are popped, so the span nests in them.
    # A group that names none writes exactly the operators it always did. The plates draw leaves one by one, so no span
    # reaches a plate page.
    spoken = node.actual_text
    if spoken:
        c._code.append("/Span << /ActualText <FEFF%s> >> BDC" % spoken.encode("utf-16-be").hex())
    try:
        # an INK finish, or a clear finish on an unclipped group, reaches every leaf below; a clear finish on a CLIPPED
        # group floods the clip's region instead, and its leaves keep their own paint
        floods = [f for f in node.finishes if clipped and f.kind not in _INK_FINISHES]
        reaches = [f for f in node.finishes if f not in floods]
        ctx.finishes.extend(reaches)
        for child in node.children:
            _draw_node(child, ctx)
        del ctx.finishes[len(ctx.finishes) - len(reaches):]
        for finish in floods:
            # §BH65(c)2: a CLEAR finish on a clipped group is a flood over the group's region — a matte laminate over
            # the whole lid, a gloss over a panel. The region is the plate; page 1 gets its depiction.
            _collect_plate(node, finish, ctx, region=node.clip)
            _depict_clear_finish(finish, node.clip, ctx)
    finally:
        if spoken:
            c._code.append("EMC")
    if clipped:
        ctx.clips.pop()
        ctx.frames.pop()
    ctx.alpha = saved_alpha
    if clipped or node.opacity < 1.0:
        c.restoreState()
    if masked:
        c.restoreState()
    if turned:
        ctx.frames.pop()
        c.restoreState()


def _draw_rect(node: Rect, ctx: _Ctx) -> None:
    c = ctx.c
    finishes = _finishes_in_force(node, ctx)
    for finish in finishes:
        _collect_plate(node, finish, ctx)
    if _ink_of(finishes) is not None:
        _draw_ink_finished(node, _ink_of(finishes), ctx)
        _depict_clear_finishes(finishes, _rect_segments(node), ctx, stroke=_stroke_only(node))
        return
    x, y = ctx.X(node.x), ctx.Y(node.y + node.h)   # bottom-left in PDF space
    w, h = node.w * mm, node.h * mm
    r = node.radius_mm * mm

    def draw(fill_flag, stroke_flag):
        if r > 0:
            c.roundRect(x, y, w, h, r, fill=fill_flag, stroke=stroke_flag)
        else:
            c.rect(x, y, w, h, fill=fill_flag, stroke=stroke_flag)

    if isinstance(node.fill, (GradientFill, PatternFill)):
        c.saveState()
        c.clipPath(_rrect_path(c, x, y, w, h, r), stroke=0, fill=0)
        if isinstance(node.fill, PatternFill):
            _paint_pattern(node.fill, (node.x, node.y, node.x + node.w, node.y + node.h), ctx)   # §BH65(c)4
        else:
            _paint_gradient(node.fill, ctx)
        c.restoreState()
        if _set_stroke(node.stroke, ctx):
            draw(0, 1)
            _reset_dash(node.stroke, c)
    else:
        fill_flag = _set_solid_fill(node.fill, ctx)
        stroke_flag = _set_stroke(node.stroke, ctx)
        draw(fill_flag, stroke_flag)
        _reset_dash(node.stroke, c)
    _depict_clear_finishes(finishes, _rect_segments(node), ctx, stroke=_stroke_only(node))


#: [the owner's second answer of 2026-09-25: a Path's declared fill rule -> reportlab's fill mode]
_FILL_MODES = {"nonzero": FILL_NON_ZERO, "evenodd": FILL_EVEN_ODD}


def _fill_mode(node):
    """The fill mode a node's own ``fill_rule`` asks for — ``None`` when it declares none, which is reportlab's
    canvas default (even-odd) and writes exactly the operator every path wrote before the field existed. The house
    mark drawn from its approved vector master declares "nonzero" (the owner's second answer of 2026-09-25)."""
    rule = getattr(node, "fill_rule", None)
    return None if rule is None else _FILL_MODES[rule]


def _draw_path(node: Path, ctx: _Ctx) -> None:
    c = ctx.c
    finishes = _finishes_in_force(node, ctx)
    for finish in finishes:
        _collect_plate(node, finish, ctx)
    if _ink_of(finishes) is not None:
        _draw_ink_finished(node, _ink_of(finishes), ctx)
        _depict_clear_finishes(finishes, node.segments, ctx, stroke=_stroke_only(node), fill_rule=node.fill_rule)
        return
    # [the owner's second answer of 2026-09-25: the fill — and a gradient's clip — by the path's own rule
    # (`_fill_mode`; None, the canvas default, for every path that declares none)]
    if isinstance(node.fill, (GradientFill, PatternFill, MeshFill)):
        c.saveState()
        c.clipPath(_segments_to_path(c, node.segments, ctx), stroke=0, fill=0, fillMode=_fill_mode(node))
        if isinstance(node.fill, PatternFill):
            _paint_pattern(node.fill, _segments_box(node.segments), ctx)                     # §BH65(c)4
        elif isinstance(node.fill, MeshFill):
            # a mesh paints at its own strength on every document — never the alpha a faded shape before it left (a
            # front's soft rooms at 30% washed 125's window out): it is new, so no exempt drawing has one to keep
            c.setFillAlpha(_alpha(ctx, 1.0))
            _paint_mesh(node.fill, ctx)                                    # [his goal of 2026-10-13, (8) and (9)]
        else:
            _paint_gradient(node.fill, ctx)
        c.restoreState()
        if _set_stroke(node.stroke, ctx):
            c.drawPath(_segments_to_path(c, node.segments, ctx), fill=0, stroke=1)
            _reset_dash(node.stroke, c)
    else:
        fill_flag = _set_solid_fill(node.fill, ctx)
        stroke_flag = _set_stroke(node.stroke, ctx)
        c.drawPath(_segments_to_path(c, node.segments, ctx),
                   fill=fill_flag, stroke=stroke_flag, fillMode=_fill_mode(node))
        _reset_dash(node.stroke, c)
    _depict_clear_finishes(finishes, node.segments, ctx, stroke=_stroke_only(node), fill_rule=node.fill_rule)


def _draw_text_legacy(node: TextRun, ctx: _Ctx) -> None:
    """The text drawer exactly as at HEAD 41604ac — §BH32(h): exempt surfaces."""
    c = ctx.c
    face = ctx.fonts.get(node.font, ctx.fonts["regular"])
    # [his goal of 2026-10-13, (10): the drawing and the layered file agree] a run that declares its case prints in it,
    # as the layered file sets it — a box carrying its product's front (125's "EYESHADOW PALETTE") draws on this
    # drawer; no run had a case at 41604ac, so none drawn then moves
    text = node.text.upper() if node.text_case == "upper" else node.text
    if node.rtl:
        from apps.dielines.exporters.text_intl import shape_ar
        # [his goal of 2026-10-10, item 6: "Arabic in a matching sans (Tajawal or Cairo), not Naskh"] a carton front's
        # Arabic in its own role's face where its document gives one; every other Arabic run in the Arabic face
        own = str(node.font or "").startswith("front-") and node.font in ctx.fonts
        face = ctx.fonts[node.font] if own else ctx.fonts["arabic"]
        text = shape_ar(text, keep_harakat=ctx.arabic_marks)          # [his rule 1] its marks, where it keeps them
        if own:
            text = _nominal_where_missing(text, face)
    c.setFont(face, node.size_pt)
    ctx.count(face, node.font or "regular", "arabic" if node.rtl else "latin", text)   # §BH32(f)
    c.setFillColor(_rl_color(node.color, ctx))
    x, y = ctx.X(node.x), ctx.Y(node.y)
    rotation = float(getattr(node, "rotation_deg", 0.0) or 0.0)
    if rotation:
        # rotate around the anchor; the run stays LIVE text (2A-6E-CORR-7)
        c.saveState()
        c.translate(x, y)
        c.rotate(rotation)
        x, y = 0.0, 0.0
    # [his goal of 2026-10-10, item 8: "The ℮ prints as a plain "e": it must be the real estimated sign everywhere."] each ℮ drawn as the sign itself, in the room its face gives it
    from apps.ire.estimated_sign import SIGN, draw_text as _draw_signed
    # … and a run that declares its letter-spacing spaced so, as the layered file spaces it (§BH65(c)8: added after
    # every glyph, the ink to the last, so centring takes one fewer); no run had tracking at 41604ac
    char_space = (node.tracking_em or 0.0) * node.size_pt
    if char_space and SIGN not in text and not node.rtl:
        from reportlab.pdfbase.pdfmetrics import stringWidth
        total = stringWidth(text, face, node.size_pt) + char_space * (len(text) - 1)
        x -= total / 2.0 if node.align == "center" else total if node.align == "right" else 0.0
        c.drawString(x, y, text, charSpace=char_space)
    else:
        _draw_signed(c, x, y, text, face, node.size_pt, node.align)
    if rotation:
        c.restoreState()


def _nominal_where_missing(text: str, face: str) -> str:
    """[His goal of 2026-10-10, item 6] ``text`` (shaped) for a face that lacks some of the isolated presentation forms
    the shaper writes (Tajawal and Cairo: alef, dal, reh, meem, waw alone) — each such form its letter's own code point,
    which the face draws as that very isolated form; every other character as it is."""
    import unicodedata

    from reportlab.pdfbase import pdfmetrics
    have = pdfmetrics.getFont(face).face.charToGlyph
    out = []
    for ch in text:
        if ord(ch) not in have and unicodedata.decomposition(ch).startswith("<isolated>"):
            base = unicodedata.normalize("NFKC", ch)
            if len(base) == 1 and ord(base) in have:
                ch = base
        out.append(ch)
    return "".join(out)


def _draw_root(root, ctx, layered: bool, used: set) -> None:
    """[His final goal, 2026-10-05, B2.] A page's root drawn — on a layered document, each of its groups inside the
    named layer it is (CUT, CREASE, GLUE, BLEED, SAFE, DIMENSIONS; ARTWORK for every other), the die in its spot plates."""
    if not layered:
        _draw_node(root, ctx)
        return
    from apps.dielines.exporters import counter_display_files as layers
    for child in root.children:
        layer = child.name if child.name in layers.CARTON_LAYERS else "ARTWORK"
        used.add(layer)
        layers.begin(ctx.c, layer)
        ctx.layer = layer
        _draw_node(child, ctx)
        ctx.layer = None
        layers.end(ctx.c)


def _attach_marks(chunks: list) -> list:
    """§BH33(3): in the VISUAL string a combining mark precedes its base, so a
    mark ``split_script_runs`` left at the tail of a Latin chunk (a mark is not
    alphanumeric, and neutrals stick to the preceding run) belongs to the
    Arabic chunk that follows it — moved there, never drawn with a Latin face."""
    import unicodedata
    out = list(chunks)
    for i in range(len(out) - 1):
        is_ar, text = out[i]
        nxt_ar, nxt = out[i + 1]
        if is_ar or not nxt_ar:
            continue
        j = len(text)
        while j and unicodedata.combining(text[j - 1]):
            j -= 1
        marks = text[j:]
        if marks:
            out[i] = (is_ar, text[:j])
            out[i + 1] = (nxt_ar, marks + nxt)
    return [(a, t) for a, t in out if t]


def _by_coverage(chunk: str, face: str, fallback: str) -> list:
    """``[(face, text)]``: ``chunk`` in ``face``, each stretch of characters ``face`` has no glyph for (and
    ``fallback`` has) drawn in ``fallback`` instead — in the chunk's own (visual) order."""
    from reportlab.pdfbase import pdfmetrics
    have = pdfmetrics.getFont(face).face.charToGlyph
    spare = pdfmetrics.getFont(fallback)
    spare_have = spare.face.charToGlyph if hasattr(spare, "face") and hasattr(spare.face, "charToGlyph") else None
    out: list = []
    for ch in chunk:
        use = face
        if ord(ch) not in have and not ch.isspace() and (spare_have is None or ord(ch) in spare_have):
            use = fallback
        if out and out[-1][0] == use:
            out[-1] = (use, out[-1][1] + ch)
        else:
            out.append((use, ch))
    return out


def _draw_text(node: TextRun, ctx: _Ctx) -> None:
    # Authored hybrid masters keep logical Unicode alongside shaped Arabic.
    # Existing documents retain their exact drawing path and PDF operators.
    logical = getattr(ctx, "logical_text", False)
    if logical:
        ctx.c._code.append("/Span << /ActualText <FEFF%s> >> BDC" % node.text.encode("utf-16-be").hex())
    try:
        _draw_text_content(node, ctx)
    finally:
        if logical:
            ctx.c._code.append("EMC")


def _draw_text_content(node: TextRun, ctx: _Ctx) -> None:
    """§BH32(e) W2: the run is split per script and each chunk meets only the
    face the layer verified for that script and role; a chunk whose role was
    refused is NOT drawn (recorded in ``ctx.skipped``) — never a Latin-only
    face for Arabic, never an unverified face for anything. §BH32(h): an
    exempt surface draws exactly as at 41604ac."""
    if ctx.exempt:
        _draw_text_legacy(node, ctx)
        return
    from apps.dielines.exporters.text_intl import shape_ar, split_script_runs
    from apps.ire.font_roles import ARABIC_ROLE_FOR, base_role, is_lead
    from apps.ire.text_script import ARABIC, scripts_in
    from reportlab.pdfbase.pdfmetrics import stringWidth
    c = ctx.c
    role = base_role(node.font or "regular")
    # §BH67(c)5: a lead alias draws in ITS face (the concept's, verified by the layer); every other run in its role's
    from apps.ire.font_roles import line_face_scripts
    own_latin, own_arabic = line_face_scripts(node.font)
    # [Day 8] a line's own face draws the script it carries: an Arabic face the line names draws its Arabic, and a face
    # with no Latin leaves the run's Latin to the role's face
    latin_face = ((ctx.fonts.get(node.font) if is_lead(node.font) and (own_latin or not own_arabic) else None)
                  or ctx.fonts.get(role) or ctx.fonts.get(node.font or "regular"))
    arabic_face = ((ctx.fonts.get(node.font) if own_arabic else None)
                   or ctx.fonts.get(ARABIC_ROLE_FOR.get(role, "arabic-body")))
    # §BH65(c)8: the run prints in its case; the record keeps its words
    drawn_text = node.text.upper() if node.text_case == "upper" else node.text
    if ARABIC in scripts_in(drawn_text):
        # visual order; §BH33(3): harakat and tanween KEPT on a non-exempt surface
        chunks = _attach_marks(split_script_runs(shape_ar(drawn_text, keep_harakat=True)))
    else:
        chunks = [(False, drawn_text)]
    pieces = []
    for is_ar, chunk in chunks:
        face = arabic_face if is_ar else latin_face
        if not face:
            ctx.skipped.append({"name": node.name, "role": role,
                                "script": "arabic" if is_ar else "latin",
                                "text": chunk})
            continue
        if is_ar and latin_face:
            # [his second look at 117, 2026-10-02: an Arabic line's "•"] a mark the Arabic face has no glyph for —
            # Noto Naskh Arabic has no "•" nor "·" — is drawn in the run's Latin face, never dropped unseen
            pieces.extend(_by_coverage(chunk, face, latin_face))
            continue
        pieces.append((face, chunk))
    if not pieces:
        return
    # §BH65(c)8: tracking is added after every glyph; the ink runs to the last glyph, so centring takes one fewer
    char_space = (node.tracking_em or 0.0) * node.size_pt
    from apps.ire.estimated_sign import width as _signed_width       # [his goal of 2026-10-12, (5)] a 3 mm ℮'s room
    total = sum(_signed_width(t, face, node.size_pt) + char_space * len(t) for face, t in pieces) - char_space * (
        1 if char_space else 0)
    finishes = _finishes_in_force(node, ctx)
    for finish in finishes:
        _collect_plate(node, finish, ctx)
    ink = _ink_of(finishes)
    c.setFillColor(_rl_color(ink.appearance if (ink is not None and ink.appearance is not None) else node.color,
                             ctx))
    if not ctx.exempt:
        c.setFillAlpha(_alpha(ctx, 1.0))   # [his goal of 2026-10-12, (3)] a line of words at its own fade
    if ctx.colour_doc is not None and not any(t for _, t in pieces):
        # §BH50(f)(7): a run with no glyph applies no colour — reportlab writes no show operator for an empty
        # string — so its colour-set call is taken back out of the counter; the operator itself stays, so no byte
        # moves. Counted, it would read "counted but not applied" against a correct page: a false disagreement.
        from apps.ire.colour_roles import resolve_fill as _resolve_fill
        _hex = _resolve_fill(ctx.colour_doc, node.color, cache=ctx.colour_cache)["hex"]
        ctx.colour_usage[_hex] -= 1
        if not ctx.colour_usage[_hex]:
            del ctx.colour_usage[_hex]
    x, y = ctx.X(node.x), ctx.Y(node.y)
    rotation = float(getattr(node, "rotation_deg", 0.0) or 0.0)
    if rotation:
        # rotate around the anchor; the run stays LIVE text (2A-6E-CORR-7)
        c.saveState()
        c.translate(x, y)
        c.rotate(rotation)
        x, y = 0.0, 0.0
    if node.align == "center":
        x -= total / 2.0
    elif node.align == "right":
        x -= total
    from apps.ire.estimated_sign import SIGN, draw_text as _draw_signed
    for face, t in pieces:
        c.setFont(face, node.size_pt)
        if char_space and SIGN not in t:
            c.drawString(x, y, t, charSpace=char_space)                # §BH65(c)8
        else:
            _draw_signed(c, x, y, t, face, node.size_pt)               # [his goal of 2026-10-10, item …] each ℮ drawn as the sign
        x += _signed_width(t, face, node.size_pt) + char_space * len(t)
        ctx.count(face, role, "arabic" if face == arabic_face and face != latin_face else "latin", t)
    if rotation:
        c.restoreState()


def _draw_barcode(node: Barcode, ctx: _Ctx) -> None:
    """EAN-13 / QR as native VECTOR (reportlab graphics), never a raster."""
    c = ctx.c
    if not ctx.exempt:
        # [his goal of 2026-10-12, (3)] its own fade — never a faded shape's drawn before it: a code must scan
        c.setFillAlpha(_alpha(ctx, 1.0))
        c.setStrokeAlpha(_alpha(ctx, 1.0))
    from reportlab.graphics import renderPDF
    x0, y0 = ctx.X(node.x), ctx.Y(node.y + node.h)
    try:
        from reportlab.lib.colors import CMYKColor
        black_c = CMYKColor(0, 0, 0, 1)     # CMYK ink — no RGB operators
        if node.symbology == "ean13":
            from reportlab.graphics.barcode import createBarcodeDrawing
            digits = "".join(ch for ch in node.value if ch.isdigit())
            if len(digits) not in (12, 13):
                return
            d = createBarcodeDrawing("EAN13", value=digits,
                                     barHeight=node.h * mm, humanReadable=True,
                                     barFillColor=black_c, textColor=black_c)
            # §BH32(f): the widget draws the human-readable digits itself, in
            # reportlab's built-in Helvetica — a face outside the layer,
            # counted here as what it is so the record and the artefact agree
            ctx.count("Helvetica", "barcode-digits", "neutral", digits)
            sc = (node.w * mm) / d.width if d.width else 1.0
            c.saveState()
            c.translate(x0, y0)
            c.scale(sc, sc)
            renderPDF.draw(d, c, 0, 0)
            c.restoreState()
        else:  # qr
            from reportlab.graphics.barcode.qr import QrCodeWidget
            from reportlab.graphics.shapes import Drawing
            q = QrCodeWidget(node.value, barFillColor=black_c)
            b = q.getBounds()
            side = min(node.w, node.h) * mm
            dq = Drawing(side, side, transform=[side / (b[2] - b[0]), 0, 0,
                                                side / (b[3] - b[1]), 0, 0])
            dq.add(q)
            renderPDF.draw(dq, c, x0, y0)
    except Exception:  # noqa: BLE001 — a bad code must not kill the emit
        pass


def _draw_sticker_bridge(node: StickerBridge, ctx: _Ctx) -> None:
    """Delegate the sticker region to the proven trilingual renderer. The
    emitter's X/Y (mm->pt, y-flip) and reportlab's mm are exactly the
    contract draw_info_panel expects — same as the legacy exporters."""
    from types import SimpleNamespace

    from apps.dielines.exporters.info_panel import draw_info_panel
    p = SimpleNamespace(x=node.x, y=node.y, width=node.w, height=node.h)
    if not ctx.exempt:
        ctx.c.setFillAlpha(_alpha(ctx, 1.0))    # [his goal of 2026-10-12, (3)] at its own fade
        ctx.c.setStrokeAlpha(_alpha(ctx, 1.0))
    # §BH32(f): the sticker draws its own strings through the canvas — every
    # one is counted at the canvas, under the role "sticker", so the record
    # and the artefact agree on a document that carries the sticker bridge
    with _counting_canvas(ctx, "sticker"):
        draw_info_panel(ctx.c, p, ctx.X, ctx.Y, node.info,
                        ctx.fonts["regular"], ctx.fonts["bold"], mm, keep_marks=ctx.arabic_marks,
                        ground=node.ground, layout=node.layout or None, ink=node.ink)


class _counting_canvas:
    """Count every string a widget draws through ``ctx.c`` while active: the
    instance's setFont / drawString / drawCentredString / drawRightString are
    shadowed for the duration and restored after (instance attributes, so the
    canvas's own state stays the canvas's)."""

    def __init__(self, ctx: "_Ctx", role: str):
        self.ctx, self.role, self.face = ctx, role, None

    def __enter__(self):
        c, ctx = self.ctx.c, self.ctx
        from apps.ire.text_script import ARABIC, scripts_in
        real = {n: getattr(c, n) for n in ("setFont", "drawString", "drawCentredString", "drawRightString")}
        self._real = real

        def set_font(name, size, leading=None):
            self.face = name
            return real["setFont"](name, size) if leading is None else real["setFont"](name, size, leading)

        def counted(method):
            def draw(x, y, text, *a, **k):
                if str(text).strip():
                    ctx.count(self.face or getattr(c, "_fontname", "") or "", self.role,
                              "arabic" if ARABIC in scripts_in(str(text)) else "latin", str(text))
                return method(x, y, text, *a, **k)
            return draw
        c.setFont = set_font
        c.drawString = counted(real["drawString"])
        c.drawCentredString = counted(real["drawCentredString"])
        c.drawRightString = counted(real["drawRightString"])
        return self

    def __exit__(self, *exc):
        for n in self._real:
            try:
                delattr(self.ctx.c, n)
            except AttributeError:
                pass
        return False


def _draw_image(node: Image, ctx: _Ctx) -> None:
    c = ctx.c
    if node.name in ctx.skip_images:      # §BH39(d): resolved REFERENCE for this output — not drawn
        return
    if not os.path.exists(node.src):
        return
    from reportlab.lib.utils import ImageReader
    clipped = node.clip is not None
    if clipped:
        c.saveState()
        c.clipPath(_segments_to_path(c, node.clip, ctx), stroke=0, fill=0)
    if not ctx.exempt:
        c.setFillAlpha(_alpha(ctx, 1.0))   # [his goal of 2026-10-12, (3)] a picture at its own fade
    c.drawImage(ImageReader(node.src), ctx.X(node.x), ctx.Y(node.y + node.h),
                width=node.w * mm, height=node.h * mm,
                preserveAspectRatio=False, mask="auto")
    if clipped:
        c.restoreState()


# --- §BH65(c)2: finishes -------------------------------------------------------

_INK_FINISHES = ("foil", "metallic_ink")
#: a clear finish's depiction on page 1: a gloss is a highlight across a quarter of the element, never a flood
#: (a flood would re-colour the ground every measurement reads); a relief is its outline lit and shadowed
_SHEEN = ("spot_uv", "gloss_varnish")
_RELIEF = {"emboss": 1.0, "deboss": -1.0}
_RELIEF_OFFSET_MM = 0.25


def _finishes_in_force(node, ctx: "_Ctx") -> list:
    """The element's own finishes, then every enclosing group's that reaches it — one per plate."""
    out, seen = [], set()
    for finish in list(node.finishes) + list(reversed(ctx.finishes)):
        if finish.plate not in seen:
            seen.add(finish.plate)
            out.append(finish)
    return out


def _ink_of(finishes):
    """The one INK finish that paints the element — the first; an element prints in one metal."""
    return next((f for f in finishes if f.kind in _INK_FINISHES), None)


def _stroke_only(node) -> bool:
    return getattr(node, "fill", None) is None and getattr(node, "stroke", None) is not None


def _rect_segments(node):
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    return [MoveTo(x=node.x, y=node.y), LineTo(x=node.x + node.w, y=node.y),
            LineTo(x=node.x + node.w, y=node.y + node.h), LineTo(x=node.x, y=node.y + node.h), ClosePath()]


def _collect_plate(node, finish, ctx: "_Ctx", region=None) -> None:
    entry = ctx.plates.setdefault(finish.plate, {"kind": finish.kind, "items": []})
    # [his goal of 2026-10-13, (2)] the clips and turns in force, in order (a region is its own group's last clip)
    frames = list(ctx.frames)
    if region is not None and frames and frames[-1][0] == "clip":
        frames = frames[:-1]
    entry["items"].append((node, frames, region))


def _draw_ink_finished(node, finish, ctx: "_Ctx") -> None:
    """An INK finish on a Path or Rect: the element prints in the finish, so page 1 draws it in the finish's
    depiction — its fill and its stroke both — and keeps its geometry and its stroke's weight."""
    from apps.ire.graph import GradientFill, SolidFill, Stroke
    paint = finish.appearance or (node.fill.color if isinstance(node.fill, SolidFill) else None)
    if paint is None and isinstance(node.fill, GradientFill):
        # [His goal after the pitch page, 2026-10-15, A (2)] a metal part drawn as its concept shows it — its light as
        # a gradient — prints on its foil plate as its shape; page 1 draws it as drawn, never leaves it out
        twin = node.model_copy(update={"finishes": []})
        saved = ctx.finishes
        ctx.finishes = []
        try:
            _draw_node(twin, ctx)
        finally:
            ctx.finishes = saved
        return
    if paint is None and node.stroke is not None:
        paint = node.stroke.color
    if paint is None:
        return
    fill = SolidFill(color=paint, opacity=getattr(node.fill, "opacity", 1.0)) if node.fill is not None else None
    stroke = (Stroke(color=paint, width_mm=node.stroke.width_mm, dash=node.stroke.dash, opacity=node.stroke.opacity)
              if node.stroke is not None else None)
    twin = node.model_copy(update={"fill": fill, "stroke": stroke, "finishes": []})
    saved = ctx.finishes
    ctx.finishes = []
    try:
        _draw_node(twin, ctx)
    finally:
        ctx.finishes = saved


def _depict_clear_finishes(finishes, segments, ctx: "_Ctx", stroke: bool = False, fill_rule=None) -> None:
    for finish in finishes:
        if finish.kind not in _INK_FINISHES:
            _depict_clear_finish(finish, segments, ctx, stroke=stroke, fill_rule=fill_rule)


def _depict_clear_finish(finish, segments, ctx: "_Ctx", stroke: bool = False, fill_rule=None) -> None:
    """Page 1's DEPICTION of a clear finish — never its plate. A matte laminate has none: matte is the absence of
    shine. A gloss is a highlight across the upper quarter of the element's box; a relief is its outline lit from
    the upper left and shadowed to the lower right (reversed for a deboss).

    [The owner's second answer of 2026-09-25: ``fill_rule`` — the element's own, when it declares one — clips a
    gloss by the rule the element fills by; None is the canvas default, as before.]"""
    from apps.ire.graph import Color
    kind = finish.kind
    if kind not in _SHEEN and kind not in _RELIEF:
        return
    c = ctx.c
    xs = [v for s in segments for v in (getattr(s, "x", None), getattr(s, "x1", None), getattr(s, "x2", None))
          if v is not None]
    ys = [v for s in segments for v in (getattr(s, "y", None), getattr(s, "y1", None), getattr(s, "y2", None))
          if v is not None]
    if not xs or not ys:
        return
    c.saveState()
    if kind in _SHEEN:
        c.clipPath(_segments_to_path(c, segments, ctx), stroke=0, fill=0,
                   fillMode=None if fill_rule is None else _FILL_MODES[fill_rule])
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        band = (y1 - y0) * 0.25
        p = c.beginPath()
        p.moveTo(ctx.X(x0), ctx.Y(y0))
        p.lineTo(ctx.X(x1), ctx.Y(y0))
        p.lineTo(ctx.X(x0), ctx.Y(y0 + band * 2.0))
        p.close()
        c.setFillColor(_rl_color(Color.from_hex("#FFFFFF"), ctx))
        c.setFillAlpha(_groups_alpha(ctx, 0.14))
        c.drawPath(p, fill=1, stroke=0)
    else:
        sign = _RELIEF[kind]
        for dx, hex_, alpha in ((-_RELIEF_OFFSET_MM * sign, "#FFFFFF", 0.55), (_RELIEF_OFFSET_MM * sign, "#000000", 0.22)):
            p = c.beginPath()
            for s in segments:
                if s.op == "M":
                    p.moveTo(ctx.X(s.x + dx), ctx.Y(s.y + dx))
                elif s.op == "L":
                    p.lineTo(ctx.X(s.x + dx), ctx.Y(s.y + dx))
                elif s.op == "C":
                    p.curveTo(ctx.X(s.x1 + dx), ctx.Y(s.y1 + dx), ctx.X(s.x2 + dx), ctx.Y(s.y2 + dx),
                              ctx.X(s.x + dx), ctx.Y(s.y + dx))
                elif s.op == "Z":
                    p.close()
            c.setStrokeColor(_rl_color(Color.from_hex(hex_), ctx))
            c.setStrokeAlpha(_groups_alpha(ctx, alpha))
            c.setLineWidth(0.3 * mm)
            c.drawPath(p, fill=0, stroke=1)
    c.restoreState()


def _draw_finish_plates(ctx: "_Ctx") -> dict:
    """Every plate on its OWN page after the artwork: a 100 % black mask in register with page 1, cut by the clips
    its elements were cut by, labelled with its name. Returns ``container_finish_plates/1.0``."""
    from apps.ire.container_finishes import SCHEMA
    from apps.ire.graph import Color, TextRun
    record = {"schema_version": SCHEMA, "pages": 1 + len(ctx.plates), "plates": [],
              "depiction": "page 1 DEPICTS each finish (foil in its metal, a gloss as a highlight, a relief as its "
                           "lit outline); the depiction is not a plate and is removed before plating"}
    if not ctx.plates:
        return record
    c = ctx.c
    black = Color.from_hex("#000000")
    for page, (plate, entry) in enumerate(ctx.plates.items(), start=2):
        names = []
        for node, frames, region in entry["items"]:
            c.saveState()
            for kind, frame in frames:              # [his goal of 2026-10-13, (2)] cut and turned as page 1 drew it
                if kind == "turn":
                    c.transform(*_pdf_turn(frame, ctx))
                else:
                    c.clipPath(_segments_to_path(c, frame, ctx), stroke=0, fill=0)
            c.setFillColor(_rl_color(black, ctx))
            c.setStrokeColor(_rl_color(black, ctx))
            c.setFillAlpha(1.0)
            c.setStrokeAlpha(1.0)
            if region is not None:
                c.drawPath(_segments_to_path(c, region, ctx), fill=1, stroke=0)
            elif isinstance(node, TextRun):
                _draw_node(node.model_copy(update={"color": black, "finishes": [], "opacity": 1.0,
                                                   "blend_mode": None, "shadow": None}), ctx)
            else:
                # [the owner's second answer of 2026-09-25: a node with no segments is cut as its BOX here — which is
                # why a mark drawn from its approved vector master is expanded into its outlines before a plate is
                # collected (`emit_pdf_ai`) — and a path is plated by its own fill rule, as page 1 drew it]
                segments = node.segments if hasattr(node, "segments") else _rect_segments(node)
                if _stroke_only(node):
                    c.setLineWidth(node.stroke.width_mm * mm)
                    c.drawPath(_segments_to_path(c, segments, ctx), fill=0, stroke=1)
                else:
                    c.drawPath(_segments_to_path(c, segments, ctx), fill=1, stroke=0, fillMode=_fill_mode(node))
            c.restoreState()
            names.append(getattr(node, "name", "") or type(node).__name__)
        _draw_node(TextRun(name=f"finish-plate-label-{plate.lower()}",
                           text=f"FINISH PLATE {plate} - {entry['kind'].upper()} - IN REGISTER WITH PAGE 1",
                           x=4.0, y=6.0, size_pt=6.0, color=black, align="left"), ctx)
        c.showPage()
        record["plates"].append({"plate": plate, "kind": entry["kind"], "page": page, "items": names})
    return record


# --- §BH65(c)7: the soft shadow -----------------------------------------------------

#: steps in a soft shadow's edge — each a copy of the silhouette at 1/N of the shadow's alpha and a wider stroke,
#: so the alpha builds from nothing at the blur's outer edge to the full shadow inside the silhouette
_SHADOW_STEPS = 8


def _shadow_shapes(node) -> list:
    """The silhouettes a shadow falls from: a Path's or a Rect's own outline; a Group's shapes, every one."""
    if isinstance(node, Group):
        return [seg for child in node.children for seg in _shadow_shapes(child)]
    if isinstance(node, Path):
        return [node.segments]
    if isinstance(node, Rect):
        return [_rect_segments(node)]
    return []


def _draw_soft_shadow(node, ctx: "_Ctx") -> None:
    """APPROXIMATED, and the contract says so: PDF has no blur. The silhouette is offset and drawn N times, each at
    1/N of the shadow's alpha, filled and stroked at a weight widening to twice the blur — where the strokes overlap
    the alpha builds, so the edge runs from nothing to the full shadow over the blur. Native vector, never a raster."""
    shadow = node.shadow
    shapes = _shadow_shapes(node)
    if not shapes:
        return
    c = ctx.c
    colour = _rl_color(shadow.color, ctx)
    step_alpha = shadow.opacity / _SHADOW_STEPS
    c.saveState()
    c.setFillColor(colour)
    c.setStrokeColor(colour)
    c.setFillAlpha(_alpha(ctx, step_alpha))
    c.setStrokeAlpha(_alpha(ctx, step_alpha))
    from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo
    dx, dy = shadow.offset_x_mm, shadow.offset_y_mm
    for segments in shapes:
        moved = []
        for s in segments:
            if isinstance(s, MoveTo):
                moved.append(MoveTo(x=s.x + dx, y=s.y + dy))
            elif isinstance(s, LineTo):
                moved.append(LineTo(x=s.x + dx, y=s.y + dy))
            elif isinstance(s, CubicTo):
                moved.append(CubicTo(x1=s.x1 + dx, y1=s.y1 + dy, x2=s.x2 + dx, y2=s.y2 + dy, x=s.x + dx, y=s.y + dy))
            else:
                moved.append(ClosePath())
        for i in range(_SHADOW_STEPS):
            c.setLineWidth(max(shadow.blur_mm * 2.0 * (1.0 - i / _SHADOW_STEPS), 0.01) * mm)
            c.drawPath(_segments_to_path(c, moved, ctx), fill=1, stroke=1)
    c.restoreState()


# --- §BH65(c)6: the soft mask ----------------------------------------------------

#: grey steps in a mask form — a luminosity change of 1/64 per step, under what the eye separates on a fade
_MASK_STEPS = 64


def _soft_mask_state(mask, ctx: "_Ctx") -> str:
    """Write a luminosity SOFT MASK for ``mask`` and return the ExtGState name that sets it. The mask is a form of
    grey steps (white keeps, black drops) declared a DeviceGray TRANSPARENCY GROUP — measured: without that
    declaration macOS's renderer (the preview's sips) ignores the mask and paints at full alpha, while MuPDF honours
    it; with it, both fade. Steps, not a shading: a form's resources carry no shading in reportlab, and a mask whose
    shading resolves to nothing is dropped whole."""
    import math
    from reportlab.pdfbase import pdfdoc
    c = ctx.c
    ctx.masks += 1
    fname = "bh65mask%d" % ctx.masks
    page_w, page_h = c._pagesize
    a0, a1 = mask.start_opacity, mask.end_opacity
    c.beginForm(fname, 0, 0, page_w, page_h)
    if mask.kind == "linear":
        x1, y1, x2, y2 = ctx.X(mask.x1), ctx.Y(mask.y1), ctx.X(mask.x2), ctx.Y(mask.y2)
        length = max(math.hypot(x2 - x1, y2 - y1), 1e-6)
        big = math.hypot(page_w, page_h) * 2.0
        c.setFillGray(a0)
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        c.saveState()
        c.translate(x1, y1)
        c.rotate(math.degrees(math.atan2(y2 - y1, x2 - x1)))
        for i in range(_MASK_STEPS):
            c.setFillGray(a0 + (a1 - a0) * (i + 0.5) / _MASK_STEPS)
            c.rect(length * i / _MASK_STEPS, -big, length / _MASK_STEPS + 0.2, 2 * big, fill=1, stroke=0)
        c.setFillGray(a1)
        c.rect(length, -big, big, 2 * big, fill=1, stroke=0)
        c.restoreState()
    else:
        cx, cy, radius = ctx.X(mask.cx), ctx.Y(mask.cy), mask.r * mm
        c.setFillGray(a1)
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        for i in range(_MASK_STEPS):
            t = 1.0 - i / _MASK_STEPS
            c.setFillGray(a0 + (a1 - a0) * t)
            c.circle(cx, cy, radius * t, fill=1, stroke=0)
    c.endForm()
    name = pdfdoc.xObjectName(fname)
    form = c._doc.idToObject[name]
    stream = pdfdoc.PDFStream()
    stream.content = form.stream
    stream.dictionary["Group"] = pdfdoc.PDFDictionary({"S": pdfdoc.PDFName("Transparency"),
                                                        "CS": pdfdoc.PDFName("DeviceGray")})
    form.Contents = stream
    smask = pdfdoc.PDFDictionary({"Type": pdfdoc.PDFName("Mask"), "S": pdfdoc.PDFName("Luminosity"),
                                  "G": pdfdoc.PDFObjectReference(name)})
    state = "gRLs%d" % len(c._extgstate._c)
    c._extgstate._c[("SMask", smask)] = state
    return state


# --- paint / geometry helpers ------------------------------------------------


def _rl_color(color, ctx: "_Ctx | None" = None) -> RLColor:
    # §BH39(e): the colour layer — on a NON-exempt document a colour the
    # composer declared as a ROLE resolves through colour_roles to brand_gov
    # (or an admitted PRODUCTION candidate); every resolved colour is counted
    # for colour_usage/1.0. An exempt document draws the literal, as today.
    if ctx is not None and ctx.colour_doc is not None:
        from apps.ire.colour_roles import resolve_fill
        row = resolve_fill(ctx.colour_doc, color, cache=ctx.colour_cache)
        ctx.colour_usage[row["hex"]] = ctx.colour_usage.get(row["hex"], 0) + 1
        color = row["color"]
    # Prefer the print-intent CMYK override when the graph carries one
    # (Illustrator then opens the object as a native CMYK fill/stroke — the
    # Gate-2 "no RGB artwork" requirement). RGB remains the screen fallback.
    if color.cmyk is not None:
        from reportlab.lib.colors import CMYKColor
        return CMYKColor(*color.cmyk)
    return RLColor(color.r, color.g, color.b)


def _segments_to_path(c, segments, ctx):
    p = c.beginPath()
    for s in segments:
        if s.op == "M":
            p.moveTo(ctx.X(s.x), ctx.Y(s.y))
        elif s.op == "L":
            p.lineTo(ctx.X(s.x), ctx.Y(s.y))
        elif s.op == "C":
            p.curveTo(ctx.X(s.x1), ctx.Y(s.y1), ctx.X(s.x2), ctx.Y(s.y2),
                      ctx.X(s.x), ctx.Y(s.y))
        elif s.op == "Z":
            p.close()
    return p


_BEZIER_K = 0.5522847498307936


def _rrect_path(c, x, y, w, h, r):
    """Path object for a (rounded) rectangle in PDF coords — used as the clip
    when painting a gradient into a Rect."""
    p = c.beginPath()
    if r <= 0:
        p.moveTo(x, y)
        p.lineTo(x + w, y)
        p.lineTo(x + w, y + h)
        p.lineTo(x, y + h)
        p.close()
        return p
    r = min(r, w / 2.0, h / 2.0)
    k = r * _BEZIER_K
    p.moveTo(x + r, y)
    p.lineTo(x + w - r, y)
    p.curveTo(x + w - r + k, y, x + w, y + r - k, x + w, y + r)
    p.lineTo(x + w, y + h - r)
    p.curveTo(x + w, y + h - r + k, x + w - r + k, y + h, x + w - r, y + h)
    p.lineTo(x + r, y + h)
    p.curveTo(x + r - k, y + h, x, y + h - r + k, x, y + h - r)
    p.lineTo(x, y + r)
    p.curveTo(x, y + r - k, x + r - k, y, x + r, y)
    p.close()
    return p


def _paint_gradient(fill: GradientFill, ctx) -> None:
    """Paint an editable axial/radial gradient across the CURRENT clip region
    (the caller clips to the shape first). reportlab writes it as a real PDF
    shading, which Illustrator opens as an editable gradient."""
    c = ctx.c
    # A PDF shading needs ONE colorspace: use CMYK only when every stop
    # carries a CMYK override, otherwise fall back to RGB for all stops.
    cmyk_shading = all(s.color.cmyk is not None for s in fill.stops)
    if cmyk_shading:
        colors = [_rl_color(s.color, ctx) for s in fill.stops]
    else:
        colors = [RLColor(s.color.r, s.color.g, s.color.b) for s in fill.stops]
    if not ctx.exempt and not cmyk_shading:
        # §BH50(f)(7): every stop an RGB shading draws is COUNTED, at the literal it is drawn at, in the stops
        # counter (unit: gradient stops drawn). A CMYK shading's stops are NOT counted here: each already passed
        # through `_rl_color` above and was counted there as a colour-set call, at its resolved hex — counting it
        # again would put one stop in both counters and falsify the declared units. Counting only: no byte moves,
        # and the colour-set counter keeps its own unit and values. Before this a colour drawn only as an RGB stop
        # was never counted (cf88211: NOT DONE), and on the product the collar's rose-gold base and the product
        # fill are applied only as RGB stops.
        for s in fill.stops:
            drawn = s.color.to_hex().upper()
            ctx.colour_stops[drawn] = ctx.colour_stops.get(drawn, 0) + 1
    positions = [s.offset for s in fill.stops]
    # §BH50(d)-0, OWNER RULED 2026-09-13 (the T50 reading, taken): on a NON-exempt document a gradient draws its
    # stops' DECLARED opacity. Before, the shading painted at whatever fill alpha the previous solid fill had left
    # in the graphics state — measured on task 52: the M3 collar at 0.22 and July's at 0.55, where its seven stops
    # declare 1.0, and the product fill at 0.5 where its stops declare 0.24 / 0.48 / 0.58. A PDF shading carries one
    # alpha (a per-stop alpha needs a soft mask reportlab does not write), so it paints at its stops' opacity where
    # they agree and at their maximum where they differ — the value the fidelity reader already reports for the
    # node (container_concept_fidelity._opacity). Both callers save and restore around it, so it cannot leak.
    # An exempt document (the sticker family, the 2A handoff, the 2A-7 carton) paints exactly as before.
    if not ctx.exempt:
        c.setFillAlpha(_alpha(ctx, max(s.opacity for s in fill.stops)))
    if fill.kind == "linear":
        c.linearGradient(ctx.X(fill.x1), ctx.Y(fill.y1),
                         ctx.X(fill.x2), ctx.Y(fill.y2), colors, positions,
                         extend=True)
    else:
        c.radialGradient(ctx.X(fill.cx), ctx.Y(fill.cy), fill.r * mm,
                         colors, positions, extend=True)


def _paint_mesh(fill, ctx) -> None:
    """[His goal of 2026-10-13, (8) and (9).] A MeshFill as one Type 6 (Coons patch) shading inside the current clip —
    each patch its four straight edges and its four corners' colours, blended by the reader itself: smooth, never
    stepped. Written as a stream of its own and named in the page's resources, as reportlab's own shadings are; a mesh
    with its corners' strengths (``alphas``) painted under a soft mask of the same patches."""
    import struct

    from reportlab.pdfbase import pdfdoc

    from apps.ire.graph import Color
    c = ctx.c
    xs, ys = [], []
    for p in fill.patches:
        for i in range(4):
            xs.append(ctx.X(float(p[2 * i])))
            ys.append(ctx.Y(float(p[2 * i + 1])))
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sx, sy = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)

    def coord(x, y):
        return struct.pack(">II", int(round((x - x0) / sx * 0xFFFFFFFF)), int(round((y - y0) / sy * 0xFFFFFFFF)))

    def colour(hx):
        col = _rl_color(Color.from_hex(hx), ctx)
        return struct.pack(">HHH", *(int(round(max(0.0, min(1.0, v)) * 0xFFFF)) for v in (col.red, col.green, col.blue)))

    def strength(v):
        return struct.pack(">H", int(round(max(0.0, min(1.0, float(v))) * 0xFFFF)))

    def mesh(corners, space, decode) -> "pdfdoc.PDFStream":
        data = bytearray()
        for p, inks in zip(fill.patches, corners):
            pts = [(ctx.X(float(p[2 * i])), ctx.Y(float(p[2 * i + 1]))) for i in range(4)]
            # the twelve control points of a patch with straight edges, round it from its first corner
            ring = []
            for i in range(4):
                a, b = pts[i], pts[(i + 1) % 4]
                ring += [a, (a[0] + (b[0] - a[0]) / 3.0, a[1] + (b[1] - a[1]) / 3.0),
                         (a[0] + 2.0 * (b[0] - a[0]) / 3.0, a[1] + 2.0 * (b[1] - a[1]) / 3.0)]
            data += b"\x00"
            for x, y in ring:
                data += coord(x, y)
            for v in inks:
                data += v
        return pdfdoc.PDFStream(dictionary=pdfdoc.PDFDictionary({
            "ShadingType": 6, "ColorSpace": pdfdoc.PDFName(space), "BitsPerCoordinate": 32, "BitsPerComponent": 16,
            "BitsPerFlag": 8, "Decode": pdfdoc.PDFArray([x0, x0 + sx, y0, y0 + sy] + decode)}),
            content=bytes(data), filters=[])

    if fill.alphas is not None:
        # [his goal of 2026-10-13, (8)] its corners' strengths as a soft mask of the same patches, blended by the reader
        # as the colours are: a glow fades to nothing over whatever is drawn beneath it, as it does under a real blur
        ground = mesh([[strength(v) for v in a] for a in fill.alphas], "DeviceGray", [0, 1])
        form = pdfdoc.PDFStream(dictionary=pdfdoc.PDFDictionary({
            "Type": pdfdoc.PDFName("XObject"), "Subtype": pdfdoc.PDFName("Form"),
            "BBox": pdfdoc.PDFArray([x0, y0, x0 + sx, y0 + sy]),
            "Group": pdfdoc.PDFDictionary({"S": pdfdoc.PDFName("Transparency"), "CS": pdfdoc.PDFName("DeviceGray")}),
            "Resources": pdfdoc.PDFDictionary({"Shading": pdfdoc.PDFDictionary({"Sa": c._doc.Reference(ground)})})}),
            content=b"/Sa sh", filters=[])
        mask = pdfdoc.PDFDictionary({"Type": pdfdoc.PDFName("Mask"), "S": pdfdoc.PDFName("Luminosity"),
                                     "G": c._doc.Reference(form)})
        # a state of the page's own graphics states, set inside the caller's saved state (it ends with it)
        states = c._extgstate._c
        name = states.setdefault(("SMask", mask), "gRLs%d" % len(states))
        c._code.append("/%s gs" % name)
    c.shade(mesh([[colour(hx) for hx in p[8:12]] for p in fill.patches], "DeviceRGB", [0, 1, 0, 1, 0, 1]))


def _segments_box(segments) -> tuple:
    xs = [v for s in segments for v in (getattr(s, "x", None), getattr(s, "x1", None), getattr(s, "x2", None))
          if v is not None]
    ys = [v for s in segments for v in (getattr(s, "y", None), getattr(s, "y1", None), getattr(s, "y2", None))
          if v is not None]
    return (min(xs), min(ys), max(xs), max(ys)) if xs and ys else (0.0, 0.0, 0.0, 0.0)


def _paint_pattern(fill, box, ctx) -> None:
    """§BH65(c)4 — paint a PatternFill across ``box`` (doc mm: x0, y0, x1, y1) inside the CURRENT clip (the caller
    clips to the shape first), as native vector marks in the fill's one colour."""
    import math
    import random
    c = ctx.c
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    colour = _rl_color(fill.color, ctx)
    step = fill.spacing_mm
    if fill.kind in ("lines", "crosshatch", "rings", "grain"):
        c.setStrokeColor(colour)
        c.setStrokeAlpha(_alpha(ctx, fill.opacity))
        c.setLineWidth(fill.weight_mm * mm)
    else:
        c.setFillColor(colour)
        c.setFillAlpha(_alpha(ctx, fill.opacity))
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    reach = math.hypot(w, h) / 2.0
    if fill.kind in ("lines", "crosshatch"):
        for angle in ((fill.angle_deg,) if fill.kind == "lines" else (fill.angle_deg, fill.angle_deg + 90.0)):
            a = math.radians(angle)
            dx, dy = math.cos(a), math.sin(a)          # along the line
            nx, ny = -dy, dx                           # across it
            p = c.beginPath()
            k = -reach
            while k <= reach:
                px, py = cx + nx * k, cy + ny * k
                p.moveTo(ctx.X(px - dx * reach), ctx.Y(py - dy * reach))
                p.lineTo(ctx.X(px + dx * reach), ctx.Y(py + dy * reach))
                k += step
            c.drawPath(p, fill=0, stroke=1)
    elif fill.kind == "rings":
        p = c.beginPath()
        r = step
        while r <= reach:
            p.circle(ctx.X(cx), ctx.Y(cy), r * mm)
            r += step
        c.drawPath(p, fill=0, stroke=1)
    elif fill.kind == "dots":
        p = c.beginPath()
        row, y = 0, y0
        while y <= y1 + step:
            x = x0 + (step / 2.0 if row % 2 else 0.0)
            while x <= x1 + step:
                p.circle(ctx.X(x), ctx.Y(y), fill.weight_mm * mm / 2.0)
                x += step
            y += step * 0.866
            row += 1
        c.drawPath(p, fill=1, stroke=0)
    else:   # grain — seeded short marks, one per spacing-square on average
        rng = random.Random(fill.seed)
        p = c.beginPath()
        for _ in range(max(1, int(w * h / (step * step)))):
            gx, gy = x0 + rng.random() * w, y0 + rng.random() * h
            a = rng.random() * math.pi
            half = step * 0.25
            p.moveTo(ctx.X(gx - math.cos(a) * half), ctx.Y(gy - math.sin(a) * half))
            p.lineTo(ctx.X(gx + math.cos(a) * half), ctx.Y(gy + math.sin(a) * half))
        c.drawPath(p, fill=0, stroke=1)


def _set_solid_fill(fill, ctx) -> int:
    c = ctx.c
    if not isinstance(fill, SolidFill):
        return 0
    c.setFillColor(_rl_color(fill.color, ctx))
    c.setFillAlpha(_alpha(ctx, fill.opacity))
    return 1


def _set_stroke(stroke, ctx) -> int:
    c = ctx.c
    if stroke is None:
        return 0
    c.setStrokeColor(_rl_color(stroke.color, ctx))
    if ctx.layer in ("CUT", "CREASE"):
        # [his final goal, B2] the die's lines on their spot plates, overprinting the artwork under them
        from apps.dielines.exporters import counter_display_files as layers
        c.setStrokeColor(layers.spot(ctx.layer))
        c.setStrokeOverprint(True)
    c.setLineWidth(stroke.width_mm * mm)
    c.setStrokeAlpha(_alpha(ctx, stroke.opacity))
    if stroke.dash:
        c.setDash(stroke.dash[0] * mm, stroke.dash[1] * mm)
    return 1


def _reset_dash(stroke, c) -> None:
    if stroke and stroke.dash:
        c.setDash()
