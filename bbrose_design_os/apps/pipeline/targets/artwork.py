"""Artwork targets (§BH55 Phase 2, 2026-09-19) — the target SDK, and its first target.

OWNER STANDING ORDER §BH55, PHASE 2: "EVERY REMAINING TARGET … No target reads COMING SOON when this phase ends." The
roadmap asked for this before the fourth target: "Target SDK (Q11) before Display Stand — the fourth target must not be
a fourth copy-paste" (docs/roadmap/master_roadmap_v3.md:200-205). An ``ArtworkTarget`` is DECLARED, not re-implemented:
its formats (the deliverables, at their true sizes), the words of the brief that choose among them, and the directive
that tells the concept what to depict. The shared pipeline does the rest — directions, three concepts, Gate 1 — and
after Gate 1 this module composes every format around the approved concept (``apps/ire/compose_artwork.py``), emits
one print file (a page per format, each at its true size), one presentation sheet (the picture the design's gate
shows, and its .ai), and pauses at the design's gate with every measurement on the record.

WHAT A FORMAT'S RECORD HOLDS, and what holds it at Gate 2: every run of type measured in the face it is drawn with
against the box it was set in, the logo's placement against the owner's own rules, the key visual's pixels per inch as
placed. A code holds the design; nothing unmeasured is marked passed. PRINT READINESS IS NOT ESTABLISHED, and said:
no print-resolution floor for a placed picture is on record here (the acceptance-time list, entry 8), and no output
intent is configured (the queue's "CMYK print intent", Phase 4) — neither is answered here.

A REVISION goes back to Gate 1: an artwork design is composed from the concept approved there, so a Gate-2 rejection
returns the task to it (views.py, Gate2RejectView) and the next approval composes the task's ONE output again, the
earlier design kept on its record.
"""
from __future__ import annotations

import os
import re
import tempfile

from apps.ire.compose_artwork import ArtworkCopy, ArtworkFormat, px_format
from apps.pipeline.targets.base import DesignTarget, TargetStrategy

RECORD_KEY = "artwork_record/1.0"
BACKEND = "artwork"


def is_artwork_target(design_target) -> bool:
    """True for a design target registered as an artwork target (not merely named one)."""
    from apps.pipeline.targets import get_target
    strategy = get_target(design_target)
    return isinstance(strategy, ArtworkTarget) and strategy.name == design_target


class ArtworkTarget(TargetStrategy):
    """A flat target, declared. Subclasses set ``name``, ``label``, ``formats``, ``format_words`` and
    ``concept_directive``; nothing else is theirs to write."""

    label = ""
    formats: tuple = ()
    #: ((whole-word pattern, (format keys…)), …) — the brief's own words choose among the formats
    format_words: tuple = ()
    #: the formats made when the brief names none (empty: every format)
    default_keys: tuple = ()
    concept_directive = ""

    def concept_structure_id(self, aria):
        return None

    def concept_prompt_profile(self, aria) -> str:
        return self.concept_directive

    def fit_for(self, task):
        """A target that sizes a structure from the product returns its fit record here (apps/ire/fit_grid.py);
        none by default."""
        return None

    def extras_for(self, task, fit) -> list:
        """Panels drawn beside the pieces, and pages after them in the print file — the structure the pieces fold
        into; none by default. Each: key, label, w_mm, h_mm, draw(frame) and document()."""
        return []

    def formats_for(self, task, fit=None) -> list:
        text = (getattr(task, "task_text", "") or "").lower()
        keys = [k for words, ks in self.format_words if re.search(words, text) for k in ks]
        named = [f for f in self.formats if f.key in keys]
        return named or [f for f in self.formats if not self.default_keys or f.key in self.default_keys]

    def copy_for(self, task) -> ArtworkCopy:
        """The words the pieces carry, each with its source. The name is the product record's; with no record, the
        name the direction plan was given — and when that is only the brief's first line, it is named as such and
        holds the design (a sentence is not a product's name)."""
        from apps.ire import compose_artwork as ca
        from apps.pipeline.services import concept_design_map as dm
        product = getattr(task, "product", None)
        copy = ArtworkCopy()
        # [his answers after the fixes for design 122, 2026-10-08, (2): "the drawing must always print my brief's size"]
        # the size a piece prints is his brief's, in his words, before the product record's
        size = dm.brief_size(getattr(task, "task_text", "") or "")
        if product is not None and (product.name or "").strip():
            copy.headline, copy.headline_source = product.name.strip(), "the product record"
            parts = [product.get_category_display() if product.category else "",
                     size[0] if size else (product.net_weight or "").strip()]
            copy.subline = " · ".join(p for p in parts if p)
            copy.body = tuple(t.strip() for t in (product.description, product.how_to_use) if (t or "").strip())
            copy.body_source = "the product record" if copy.body else ""
            return copy
        from apps.pipeline.models import CreativeBrief
        brief = CreativeBrief.objects.filter(task=task).first()
        planned = ((getattr(brief, "design_intent", None) or {}).get("brief") or {})
        name = (planned.get("product_name") or "").strip()
        if name:
            copy.headline, copy.headline_source = name, "the direction plan (no product record)"
            first = next((ln.strip() for ln in (task.task_text or "").splitlines() if ln.strip()), "")
            if first and name == first[:200]:
                copy.codes.append(ca.HEADLINE_IS_THE_BRIEF)
        if size:
            copy.subline = size[0]
        return copy

    def begin_output(self, aria, approved_image):
        from apps.pipeline.services.authored_master import is_authored
        if is_authored(aria.task):
            raise ValueError("Authored masters cannot enter legacy artwork reconstruction.")
        """After Gate 1: compose every format around the approved concept, emit, measure, and pause at the design's
        gate. A failure raises — the pipeline marks the task failed with its reason."""
        from django.core.files.base import ContentFile

        from apps.ire import compose_artwork as ca
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        from apps.pipeline.models import PackagingOutput
        from apps.pipeline.targets.container import _uploaded_paths

        task = aria.task
        fit = self.fit_for(task)
        formats = self.formats_for(task, fit)
        extras = self.extras_for(task, fit)
        copy = self.copy_for(task)
        key_visual = approved_image.image_file.path if approved_image.image_file else None
        # THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo
        # trace, switch the mark to it so gold foil can print." The house mark through its one switch
        # (apps/ire/brand_mark.py): `png` is exactly the raster picked here before, `master` the approved vector
        # master when one is on file; an uploaded logo stays the task's own raster
        from apps.ire import brand_mark as _brand_mark
        _house = _brand_mark.house_mark(_uploaded_paths(task))
        logo, logo_master = _house["png"], _house["master"]
        rows = []
        # [his final goal, 2026-10-05, C7: "THE SYSTEM CHECKS ITS OWN WORK"] each format repaired before it is drawn
        # and read after
        from apps.ire import self_check as _self_check
        checked_fixed, checked_shown = [], []
        with tempfile.TemporaryDirectory() as td:
            pages = []
            for fmt in formats:
                doc, row = ca.artwork_document(fmt, copy, key_visual=key_visual, logo=logo,
                                               title=f"{copy.headline or self.label} — {fmt.label}",
                                               **_brand_mark.master_kwargs(logo_master))
                page = os.path.join(td, f"{fmt.key}.pdf")
                _regions = [{"name": fmt.label, "x": 0.0, "y": 0.0, "w": doc.page_w, "h": doc.page_h}]
                _fixed, _shown = _self_check.repair_said(doc, _regions)
                emit_pdf_ai(doc, page)
                checked_fixed += _fixed
                checked_shown += _shown + _self_check.inspect_said(page, doc, _regions)
                pages.append(page)
                if fmt.px:
                    row["png"] = _png_exact(page, fmt, td, stem=f"artwork_task_{task.id}_{fmt.key}")
                rows.append(row)
            for extra in extras:                          # a structure's drawing: a page of its own, at true size
                page = os.path.join(td, f"{extra['key']}.pdf")
                emit_pdf_ai(extra["document"](), page)
                pages.append(page)
            print_file = os.path.join(td, "artwork.pdf")
            _merge(pages, print_file)
            sheet = ca.presentation_document(formats, copy, key_visual=key_visual, logo=logo,
                                             title=f"{copy.headline or 'Untitled'} — {self.label}", extras=extras,
                                             **_brand_mark.master_kwargs(logo_master))
            sheet_ai, sheet_png = os.path.join(td, "sheet.ai"), os.path.join(td, "sheet.png")
            emit_pdf_ai(sheet, sheet_ai)
            preview_px = _render_png(sheet_ai, sheet_png, PREVIEW_DPI)
            codes = sorted({c for r in rows for c in r["codes"]} | set(copy.codes) | set((fit or {}).get("codes") or []))
            record = {
                "schema_version": RECORD_KEY, "target": self.name, "label": self.label,
                "formats": rows,
                "copy": {"headline": copy.headline, "headline_source": copy.headline_source,
                         "subline": copy.subline, "body_paragraphs": len(copy.body), "body_source": copy.body_source},
                "key_visual": {"generated_image_id": approved_image.id, "sha256": ca.file_sha256(key_visual)},
                "print_readiness": {
                    "state": "NOT_ESTABLISHED",
                    "reasons": ["no print-resolution floor for a placed picture is on record — each format's key "
                                "visual carries its pixels per inch as placed, measured, with no verdict "
                                "(the acceptance-time list, entry 8)",
                                "no output intent (ICC) is configured on this machine (the queue: CMYK print intent)"]},
                "codes": codes,
                "preview": {"dpi": PREVIEW_DPI, "px": preview_px},
            }
            if fit:
                record["fit"] = fit
            if _house["state"] in (_brand_mark.APPROVED, _brand_mark.REFUSED):
                # [the owner's second answer of 2026-09-25: the house mark's state, only when an approval is on file]
                record[_brand_mark.SCHEMA] = _brand_mark.selection_record(_house)
            # ONE output per task: a design composed again (another concept approved after a Gate-2 rejection) is
            # written over the task's own output — the status payload and his acceptance door read that one — and
            # the earlier design stays on its record: its files keep their names on disk, and its codes, concept
            # and picture hash are listed under `history`. An acceptance of the earlier picture reads VOID.
            from apps.ire import views_of as _views_of        # [his goal of 2026-10-13, (6)] each piece's place
            spec = {"backend": BACKEND, "design_target": self.name, "product_name": copy.headline, RECORD_KEY: record,
                    _self_check.SCHEMA: _self_check.record(checked_fixed, checked_shown),
                    _views_of.SCHEMA: _views_of.views(sheet)}
            output = task.packaging_outputs.order_by("id").first()
            if output is not None and (output.spec_sheet or {}).get("backend") == BACKEND:
                prior = output.spec_sheet or {}
                history = list(prior.get("history") or [])
                history.append({"generated_image_id": output.approved_image_id,
                                "codes": (prior.get(RECORD_KEY) or {}).get("codes"),
                                "preview": output.design_preview.name or "",
                                "preview_sha256": ca.file_sha256(output.design_preview.path)
                                if output.design_preview else None,
                                "gate_2_revision_note": prior.get("gate_2_revision_note", "")})
                spec["history"] = history
                output.approved_image = approved_image
                output.spec_sheet = spec
                output.is_final_approved = False
            else:
                output = PackagingOutput.objects.create(task=task, approved_image=approved_image, spec_sheet=spec)
            stem = f"artwork_task_{task.id}"
            with open(print_file, "rb") as fh:
                output.production_pdf.save(f"{stem}.pdf", ContentFile(fh.read()), save=False)
            with open(sheet_ai, "rb") as fh:
                output.design_preview_ai.save(f"{stem}.ai", ContentFile(fh.read()), save=False)
            if os.path.exists(sheet_png):
                with open(sheet_png, "rb") as fh:
                    output.design_preview.save(f"{stem}.png", ContentFile(fh.read()), save=False)
            output.save()
        aria._prepare_views(output)                  # [his goal of 2026-10-13, (6)] its views made with it
        task.status = "awaiting_gate_2"
        task.save()
        aria.log(f"ARIA: {self.label} composed — {len(rows)} format(s)"
                 + (f"; held by {', '.join(codes)}" if codes else "; every run measured and held"),
                 payload={"formats": [r["key"] for r in rows], "codes": codes})

    def review_sections(self, task) -> list[dict]:
        output = task.packaging_outputs.order_by("-id").first()
        record = ((output.spec_sheet or {}).get(RECORD_KEY) if output else None) or {}
        rows = [{"label": "Design target", "value": self.label}]
        for r in record.get("formats") or []:
            size = (f'{r["px"][0]} × {r["px"][1]} px' if r.get("px") else
                    f'{r["trim_mm"][0]:g} × {r["trim_mm"][1]:g} mm' + (f' + {r["bleed_mm"]:g} mm bleed' if r["bleed_mm"] else ""))
            kv = r.get("key_visual") or {}
            ppi = f' · picture {kv["effective_ppi"]:g} ppi as placed' if kv.get("effective_ppi") else ""
            rows.append({"label": r["label"], "value": size + ppi})
        if record:
            codes = record.get("codes") or []
            rows.append({"label": "Type and logo", "value": ("every run measured and held" if not codes
                                                             else "held: " + ", ".join(codes))})
            rows.append({"label": "Print readiness", "value": "NOT ESTABLISHED — no print-resolution floor or "
                                                              "output intent on record"})
            fit = record.get("fit") or {}
            if fit.get("tray"):
                a, t, h = fit["arrangement"], fit["tray"], fit["header"]
                rows.append({"label": "Structure (provisional)",
                             "value": f'{a["columns"]} × {a["rows"]} = {fit["units"]} units · tray '
                                      f'{t["outer_w_mm"]:g} × {t["outer_d_mm"]:g} mm · header card '
                                      f'{h["w_mm"]:g} × {h["h_mm"]:g} mm — a converter\'s die governs'})
        return rows


#: the picture the design's gate shows is rendered at the resolution `apps/ire/rasterize.pdf_to_png` itself declares
#: as its default — on this machine that function hands the file to `sips`, which renders at the page's native 72 dpi
#: and ignores it (measured: a 355 × 223 mm sheet came back 1007 × 632 px, its small copy unreadable)
PREVIEW_DPI = 150


def _render_png(pdf_path, out_png, dpi) -> list:
    """Page 1 at ``dpi``, measured back from the file: [width, height] in px."""
    import fitz
    with fitz.open(pdf_path) as doc:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0), alpha=False)
        pix.save(out_png)
        return [pix.width, pix.height]


def _merge(pages, out_path) -> None:
    """One print file, a page per format, each page its own true size."""
    import fitz
    with fitz.open() as merged:
        for p in pages:
            with fitz.open(p) as src:
                merged.insert_pdf(src)
        merged.save(out_path)


def _png_exact(page_pdf, fmt: ArtworkFormat, td, *, stem: str) -> dict:
    """A digital format rendered at its exact pixel size — the file a channel takes — saved to storage beside the
    design's other files, and measured back from the file it wrote."""
    import hashlib

    import fitz
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    with fitz.open(page_pdf) as doc:
        page = doc[0]
        zx, zy = fmt.px[0] / page.rect.width, fmt.px[1] / page.rect.height
        pix = page.get_pixmap(matrix=fitz.Matrix(zx, zy), alpha=False)
        path = os.path.join(td, f"{fmt.key}.png")
        pix.save(path)
    with open(path, "rb") as fh:
        data = fh.read()
    from PIL import Image as _PIL
    with _PIL.open(path) as im:
        size = list(im.size)
    name = default_storage.save(f"dielines/{stem}.png", ContentFile(data))
    return {"px": size, "exact": size == list(fmt.px), "name": name, "url": default_storage.url(name),
            "sha256": hashlib.sha256(data).hexdigest()}


class MarketingMaterialTarget(ArtworkTarget):
    """Printed collateral around the product: an A5 leaflet (its cover and the product's own words on its back) and an
    A4 poster — or the pieces the brief names."""

    name = DesignTarget.MARKETING_MATERIAL.value
    label = "Marketing Material"
    formats = (
        ArtworkFormat("a5_leaflet_front", "A5 leaflet — front", 148.0, 210.0, bleed_mm=3.0, safe_mm=6.0),
        ArtworkFormat("a5_leaflet_back", "A5 leaflet — back", 148.0, 210.0, bleed_mm=3.0, safe_mm=6.0, layout="info"),
        ArtworkFormat("a4_poster", "A4 poster", 210.0, 297.0, bleed_mm=3.0, safe_mm=8.0),
        ArtworkFormat("a6_postcard", "A6 postcard", 105.0, 148.0, bleed_mm=3.0, safe_mm=5.0),
    )
    format_words = (
        (r"\bposters?\b", ("a4_poster",)),
        (r"\b(leaflets?|flyers?|brochures?)\b", ("a5_leaflet_front", "a5_leaflet_back")),
        (r"\bpostcards?\b", ("a6_postcard",)),
    )
    default_keys = ("a5_leaflet_front", "a5_leaflet_back", "a4_poster")
    concept_directive = (
        "This design target is MARKETING MATERIAL: printed campaign pieces (a leaflet and a poster) built around ONE "
        "KEY VISUAL. Render only that key visual: the product in an art-directed scene that carries the direction's "
        "mood, the product clear and prominent, its focal point near the centre with space around it — the frame is "
        "cropped to squarer and wider shapes for the pieces, and the product's name is set in type beside it later. "
        "Do NOT render any words, letters, numbers or logos, and no label text that can be read. Do NOT render a "
        "carton, a dieline, a technical drawing, a flat packshot on white, or a mock-up of a leaflet or poster.")


class SocialMediaTarget(ArtworkTarget):
    """Channel-sized pieces around the product: a square and a portrait post, a story and a link image — each a PNG at
    its exact pixel size, the file the channel takes — or the pieces the brief names."""

    name = DesignTarget.SOCIAL_MEDIA.value
    label = "Social Media"
    #: CHOSEN, and said as chosen: a story's type keeps 250 px clear of its top and its foot, where a platform lays its
    #: own chrome (the account line, the reply bar) over the picture — the picture itself still runs to the edges
    STORY_CHROME_PX = 250
    formats = (
        px_format("post_square", "Square post", 1080, 1080),
        px_format("post_portrait", "Portrait post (4:5)", 1080, 1350),
        px_format("story", "Story (9:16)", 1080, 1920, safe_insets_px=(STORY_CHROME_PX, 48, STORY_CHROME_PX, 48)),
        px_format("link_landscape", "Link image (1.91:1)", 1200, 628),
    )
    format_words = (
        (r"\binstagram\b", ("post_square", "post_portrait", "story")),
        (r"\bsquare\b", ("post_square",)),
        (r"\bportrait\b", ("post_portrait",)),
        (r"\b(stor(?:y|ies)|reels?|tiktok)\b", ("story",)),
        (r"\b(links?|facebook|linkedin)\b", ("link_landscape",)),
    )
    concept_directive = (
        "This design target is SOCIAL MEDIA: posts, a story and a link image built around ONE KEY VISUAL, seen on a "
        "phone. Render only that key visual: the product in a scene that carries the direction's mood — one focal "
        "subject, bold and simple enough to read small, its focal point near the centre with generous space around it "
        "— the frame is cropped to square, tall and wide shapes, and the product's name is set in type beside it later. "
        "Do NOT render any words, letters, numbers, logos, stickers, emoji, interface elements, frames or phone "
        "mock-ups; no carton and no dieline.")


class ExhibitionBoothTarget(ArtworkTarget):
    """The stand's graphics at their true sizes around one key visual: a back wall, a counter front and a roll-up banner
    — a side wall by name. SAID PLAINLY, what is not drawn: the stand's spatial design (its plan, furniture, lighting and
    visitor flow); the graphics are sized to a 3 × 3 m shell-scheme stand, and the organiser's own panel sizes govern
    the print file."""

    name = DesignTarget.EXHIBITION_BOOTH.value
    label = "Exhibition Booth"
    #: CHOSEN, and said as chosen: sizes for a 3 × 3 m shell-scheme stand, and a 5 mm bleed for large-format print —
    #: every organiser publishes its own panel sizes, and those govern the print file; none is on record here
    formats = (
        ArtworkFormat("back_wall", "Back wall graphic", 3000.0, 2400.0, bleed_mm=5.0, safe_mm=60.0),
        ArtworkFormat("counter_front", "Counter front", 1000.0, 900.0, bleed_mm=5.0, safe_mm=30.0),
        ArtworkFormat("rollup_banner", "Roll-up banner", 850.0, 2000.0, bleed_mm=5.0, safe_mm=30.0),
        ArtworkFormat("side_wall", "Side wall graphic", 3000.0, 2400.0, bleed_mm=5.0, safe_mm=60.0),
    )
    format_words = (
        (r"\bback ?walls?\b", ("back_wall",)),
        (r"\bcounters?\b", ("counter_front",)),
        (r"\b(roll-?ups?|pull-?ups?|banners?)\b", ("rollup_banner",)),
        (r"\b(side ?walls?|corner)\b", ("side_wall",)),
    )
    default_keys = ("back_wall", "counter_front", "rollup_banner")
    concept_directive = (
        "This design target is an EXHIBITION BOOTH's graphics, built around ONE KEY VISUAL printed at architectural "
        "scale: a back wall three metres wide, a counter front and a roll-up banner. Render only that key visual: the "
        "product as the hero of a scene that carries the direction's mood, bold enough to read from across a hall, its "
        "focal point near the centre with generous space around it — the frame is cropped to wide, square and tall "
        "shapes, and the product's name is set in type beside it later. Do NOT render any words, letters, numbers or "
        "logos, and no booth, stand, hall, floor plan, furniture, people or mock-up of any printed piece.")


#: the Display Stand holds a design at Gate 2 when nothing gives the unit a size — the tray cannot be sized from nothing
DISPLAY_UNIT_UNSIZED = "DISPLAY_STAND_UNIT_UNSIZED"
#: the count the brief names: "a 72-unit display", "for 24 bottles", "holds 36"
_UNIT_COUNT_WORDS = (r"(\d{1,3})\s*-?\s*(?:units?|pcs|pieces|bottles|jars|tubes|pots|sticks|pens|eyeliners?|"
                     r"lipsticks?|mascaras?|glosses|products|items)\b")
_HOLDS_WORDS = r"\b(?:holds?|holding|for)\s+(\d{1,3})\b(?!\s*(?:ml|millilit|g\b|mm|cm|%))"


class DisplayStandTarget(ArtworkTarget):
    """A counter display: a tray sized to hold the product, and a header card above it. The arrangement, the tray and
    the card are PROPOSED from the unit's own size and the count the brief names (apps/ire/fit_grid.py); the header card
    and the tray's front lip are the pieces, and the tray's flat blank is drawn beside them — PROVISIONAL, a converter's
    die governs, a colleague test-fits a printed sample (§BH70(3): never a hold on the design)."""

    name = DesignTarget.DISPLAY_STAND.value
    label = "Display Stand"
    #: CHOSEN, and said as chosen: the count the tray is proposed for when the brief names none; and the header card's
    #: size when no unit size is on record (the design is then held, DISPLAY_STAND_UNIT_UNSIZED)
    DEFAULT_UNITS = 12
    UNSIZED_HEADER_MM = (300.0, 200.0)
    concept_directive = (
        "This design target is an ASSEMBLED COUNTERTOP DISPLAY STAND, straight-on on a clean ground. "
        "The concept shows the complete stepped display with the exact attached product and geometry references. "
        "Preserve the specified product count, rows, dimensions and closures; never invent a substitute bottle. "
        "Design the header, risers and sides as a coherent object with clear brand, product name and descriptor. "
        "Concept lettering may be approximate; approved live type replaces it in production. House references "
        "supply style only. An exact product reference and an exact geometry reference are required before payment. "
        "No booth, floor fixture, extra products or all-panel wallpaper. The picture is a concept, not construction approval.")

    def fit_for(self, task) -> dict:
        from apps.ire import fit_grid
        n, n_source = _units_named(task, self.DEFAULT_UNITS)
        unit = _display_unit(task)
        if unit is None:
            return {"units": n, "count_source": n_source, "unit": None, "codes": [DISPLAY_UNIT_UNSIZED],
                    "note": "no size for the unit on the product record or in the brief — the tray is not sized"}
        fit = fit_grid.tray_for(n, unit)        # its codes: the registry's, for a structure no sample has proven
        fit.update(count_source=n_source)
        return fit

    def formats_for(self, task, fit=None) -> list:
        fit = fit if fit is not None else self.fit_for(task)
        if "tray" not in fit:
            w, h = self.UNSIZED_HEADER_MM
            return [ArtworkFormat("header_card", "Header card", w, h, bleed_mm=3.0, safe_mm=6.0)]
        hw, hh = fit["header"]["w_mm"], fit["header"]["h_mm"]
        return [ArtworkFormat("header_card", "Header card", hw, hh, bleed_mm=3.0, safe_mm=6.0),
                ArtworkFormat("front_lip", "Tray front lip", fit["tray"]["outer_w_mm"], fit["tray"]["lip_h_mm"],
                              bleed_mm=3.0, safe_mm=3.0, layout="type")]

    def extras_for(self, task, fit) -> list:
        if not fit or "tray" not in fit:
            return []
        from apps.ire import compose_artwork as ca
        w, h = ca.structure_size(fit)
        return [{"key": "structure", "label": "Structure (provisional)", "w_mm": w, "h_mm": h,
                 "draw": lambda frame: ca.compose_structure(fit, frame),
                 "document": lambda: ca.structure_document(fit)}]


def _units_named(task, default: int) -> tuple[int, str]:
    """The count the brief names, or the proposal when it names none."""
    text = (getattr(task, "task_text", "") or "").lower()
    m = re.search(_UNIT_COUNT_WORDS, text) or re.search(_HOLDS_WORDS, text)
    if m and 1 <= int(m.group(1)) <= 500:
        return int(m.group(1)), "the brief's own words"
    return default, f"PROPOSED — the brief names no count ({default}, chosen)"


def _display_unit(task):
    """The unit as it stands on the counter: the product record's own size (a carton's record IS the unit a display
    holds), else the size the container's proposal gives the capacity the brief names, else nothing."""
    from apps.ire.fit_grid import Unit
    product = getattr(task, "product", None)
    if product is not None and all(getattr(product, k, None) for k in ("width_mm", "depth_mm", "height_mm")):
        from apps.pipeline.targets.container import _record_describes_carton
        source = ("the product record — its carton, the unit as it stands on a counter"
                  if _record_describes_carton(product) else "the product record")
        return Unit(float(product.width_mm), float(product.depth_mm), float(product.height_mm), source)
    from apps.pipeline.targets.container import _bottle_size_for, _capacity_ml
    size = _bottle_size_for(_capacity_ml((getattr(task, "task_text", "") or "").lower(), product))
    if size:
        return Unit(size["width_mm"], size["width_mm"], size["height_mm"],
                    "sized from the capacity the brief names (the container's own proposal, 3938d81)")
    return None
