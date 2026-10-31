"""NATIVE_VECTOR_RECONSTRUCTION artwork composition (Phase 2A-6 §6/§8).

The standard production mode for packaging artwork. Every printed decorative
element is generated as native graph nodes — editable gradients, Bézier
paths, filled ribbons, live text — by the bounded design-language library
(:mod:`apps.ire.design_language`). No image-model call, no image tracing, no
raster panel background.

The Gate-1 render is TEMPORARY_VISUAL_REFERENCE_ONLY: it informs colour
relationships, flow direction, density, hierarchy, motif and finish INTENT
through the selected direction's own vocabulary, and never reaches the page.
When a direction cannot be responsibly rebuilt from the supported
primitives, composition raises VECTOR_RECONSTRUCTION_REVIEW_REQUIRED rather
than degrading to printable pixels.

Panel roles (§8): the front carries the strongest expression; the back stays
quiet so regulatory copy reads; sides coordinate at reduced density without
mechanically repeating the front; flaps and the glue tab get progressively
less. Each surface is generated with its OWN seed, so no two panels are the
same artwork tiled twice.

Raster policy: the only Image node permitted is the official brand logo
lockup — small, non-decorative, and flagged BRAND_LOGO_RASTER_FALLBACK until
an approved vector brand master exists.

[The owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803):
"When I approve the logo trace, switch the mark to it so gold foil can
print." Handed that approved master (``logo_master``, apps/ire/brand_mark.py),
the lockup is no raster: it is drawn from the master and carries
BRAND_MARK_VECTOR_MASTER in its name where the raster carries the fallback.]
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace

from apps.dielines.exporters.artwork_layers import artwork_targets, target_bounds
from apps.dielines.exporters.info_panel import has_info_content
from apps.ire.compose import (
    _component_clip_segments,
    _rect_clip,
    _structure_nodes,
)
from apps.ire.design_language import (
    DEFAULT_EMPHASIS,
    DesignLanguage,
    LanguageParameters,
    ROLE_BACK,
    ROLE_FRONT,
    VectorReconstructionReviewRequired,
    gen_gradient_field,
    get_language,
    panel_role,
    resolve_language,
)
from apps.ire.graph import (
    ClosePath,
    Document,
    GradientFill,
    GradientStop,
    Group,
    Image,
    LineTo,
    MoveTo,
    Path,
    Rect,
    Segment,
    SolidFill,
    StickerBridge,
    Stroke,
    TextRun,
)

_PAGE_MARGIN_MM = 10.0

#: The one production artwork mode (§6).
NATIVE_VECTOR_RECONSTRUCTION = "NATIVE_VECTOR_RECONSTRUCTION"
#: What the approved Gate-1 concept is, and all it may ever be (§6).
TEMPORARY_VISUAL_REFERENCE_ONLY = "TEMPORARY_VISUAL_REFERENCE_ONLY"
#: Flag carried by the brand logo raster until a vector master is approved.
BRAND_LOGO_RASTER_FALLBACK = "BRAND_LOGO_RASTER_FALLBACK"

#: DOMAIN (§W2(c)): VECTOR ARTWORK COMPOSITION — the smallest live text THIS
#: COMPOSER will emit, applied where it derives a size from panel geometry. It
#: is not the container's legibility floor: §W2 ruled that the
#: container_production_method capability table governs there, per run and per
#: surface (apps/ire/container_text_floor.py). Four minimum-size constants
#: disagreed in this repo and each keeps its own domain; a constant that does
#: not name its domain is a conflation waiting to happen.
_MIN_TEXT_PT = 5.5


@dataclass(frozen=True)
class VectorArtStyle:
    """WHICH design language a composition runs, and with what parameters."""
    language: str = "liquid_veil"
    parameters: LanguageParameters = field(default_factory=LanguageParameters)
    mode: str = NATIVE_VECTOR_RECONSTRUCTION

    @property
    def name(self) -> str:
        return self.language

    @property
    def seed(self) -> int:
        return self.parameters.seed

    def resolved_language(self) -> DesignLanguage:
        return get_language(self.language)

    def swatches(self) -> dict:
        return self.parameters.swatches.to_dict()

    @classmethod
    def for_direction(cls, direction: dict | None, *, seed: int = 0,
                      explicit_language: str | None = None,
                      parameters: LanguageParameters | None = None
                      ) -> "VectorArtStyle":
        """Derive the style from the SELECTED direction, or fail closed.

        Raises VectorReconstructionReviewRequired when the direction's visual
        language is outside the supported primitives — never rasterizes.
        """
        lang = resolve_language(direction, explicit=explicit_language)
        params = parameters or replace(lang.defaults, seed=seed)
        return cls(language=lang.name, parameters=params)

    @classmethod
    def for_variation(cls, variation: dict, *, seed: int = 0,
                      parameters: LanguageParameters | None = None
                      ) -> "VectorArtStyle":
        """Derive the style from the SELECTED Gate-1 VARIATION — the record
        the user actually approved (2A-6E-CORR-7). Fails closed when the
        variation's visual language is outside the supported primitives;
        never falls back to the direction, never substitutes a generic
        pattern."""
        lang = resolve_language(None, variation=variation)
        params = parameters or replace(lang.defaults, seed=seed)
        return cls(language=lang.name, parameters=params)


def compose_vector_art_graph(
    coords, *, style: VectorArtStyle | None = None, logo_path: str | None = None,
    product_name: str = "", subtitle: str = "", panel_info: dict | None = None,
    page_margin_mm: float = _PAGE_MARGIN_MM, concept_spec: dict | None = None,
    logo_master=None,
) -> Document:
    """Build a fully native-vector design Document for the dieline.

    ``concept_spec`` (2A-6E-CORR-7): the SELECTED Gate-1 variation's
    reconstruction record — its logo zone, stacked-name hierarchy, secondary
    and vertical copy, frame and finish intent drive the composition instead
    of the legacy centered-label defaults.
    """
    style = style or VectorArtStyle()
    language = style.resolved_language()
    params = style.parameters
    info = panel_info or {}
    has_info = has_info_content(info)

    min_x, min_y, max_x, max_y = coords.bleed_polygon.bounds
    vx = min_x - page_margin_mm
    vy = min_y - page_margin_mm
    vw = (max_x - min_x) + 2 * page_margin_mm
    vh = (max_y - min_y) + 2 * page_margin_mm + 8.0

    def gx(x: float) -> float:
        return x - vx

    def gy(y: float) -> float:
        return y - vy

    panels = {p.name: p for p in coords.panels}
    front = panels.get("front")
    back = panels.get("back")

    # --- Background: one editable gradient over the whole bleed silhouette --
    ground_children = [_bleed_ground(
        coords, params, gx, gy,
        ivory_dominant=bool(concept_spec))]
    if concept_spec and "mint" in str(
            concept_spec.get("color_field_signature", "")).lower() \
            and front is not None:
        # the selected concept's layered pastel depth: a faint soft-mint
        # atmospheric wash in the front's lower-left — an EDITABLE gradient
        # object (approved refs' layered-pastel influence made observable;
        # never a flat single-color ground)
        from apps.ire.design_language import SOFT_MINT_WASH
        ground_children.append(Rect(
            name="soft-mint-wash", x=gx(front.x),
            y=gy(front.y + front.height * 0.55),
            w=front.width * 0.55, h=front.height * 0.45,
            fill=GradientFill(
                kind="linear",
                stops=[GradientStop(offset=0.0,
                                    color=SOFT_MINT_WASH.color()),
                       GradientStop(offset=1.0,
                                    color=params.swatches.ground_top
                                    .color())],
                x1=gx(front.x), y1=gy(front.y + front.height),
                x2=gx(front.x + front.width * 0.55),
                y2=gy(front.y + front.height * 0.55)),
            opacity=0.28))
    grounds = Group(name="Background", role="background",
                    children=ground_children)

    # --- Decoration: the design language, per panel role --------------------
    deco_children: list = []
    surfaces: list[dict] = []
    for t in artwork_targets(coords, has_info):
        bounds = target_bounds(coords, t)
        if bounds is None:
            continue
        if t.panel is not None:
            clip = _rect_clip(t.panel, gx, gy)
            surface = t.panel.name
        else:
            clip = _component_clip_segments(coords, t.comp_id, gx, gy)
            surface = t.comp_id
            if clip is None:
                continue
        role = panel_role(surface)
        emphasis = float(params.emphasis.get(role, 0.5))
        surfaces.append({"surface": surface, "role": role,
                         "emphasis": emphasis})
        # The back panel (and any sticker face) stays quiet: regulatory
        # readability outranks decoration.
        if t.kind == "sticker" or role == ROLE_BACK or emphasis <= 0.0:
            continue
        nodes = language.build(bounds, params, role, gx, gy)
        if not nodes:
            continue
        deco_children.append(Group(
            name=f"{language.name}-{surface}", role="decoration", clip=clip,
            children=nodes))
    decoration = Group(name=f"{language.label} (vector)", role="decoration",
                       children=deco_children)

    # --- Finish accents (a named group so finishing is separable) -----------
    if concept_spec:
        # 2A-6E-CORR-7: concept-driven frame + separable finish layers
        frame_nodes = _concept_frame_nodes(front, concept_spec, params, gx, gy)
        name_nodes = _concept_type_nodes(front, concept_spec, params, gx, gy)
        finish_children = frame_nodes + _concept_finish_layers(
            front, concept_spec, params, name_nodes, gx, gy)
    else:
        name_nodes = None
        finish_children = []
        for p in (front, back):
            if p is None:
                continue
            finish_children.append(Rect(
                name=f"accent-rule-{p.name}", x=gx(p.x + p.width * 0.22),
                y=gy(p.y + p.height * 0.80), w=p.width * 0.56, h=0.4,
                fill=SolidFill(color=params.swatches.accent.color())))
    finishes = Group(name=f"{params.swatches.accent.name} accents",
                     role="effects", children=finish_children)

    # --- Logo: the sole permitted raster, explicitly flagged ----------------
    logo_zone_requested = (concept_spec or {}).get("logo_zone", "")
    zone_l = str(logo_zone_requested).lower()
    logo_zone_used = ("upper-left" if any(marker in zone_l for marker in
                      ("upper left", "upper-left", "top left", "top-left"))
                      else "centered")
    logo = Group(name="Logo", role="logo",
                 children=_logo_nodes(front, logo_path, gx, gy,
                                      zone=logo_zone_requested, logo_master=logo_master))

    # --- Typography: live editable text (front only) ------------------------
    typography = Group(name="Typography", role="typography",
                       children=(name_nodes if concept_spec
                                 else _type_nodes(front, product_name,
                                                  subtitle, params, gx, gy)))

    # --- Info face: the regulatory sticker on the quiet back panel ----------
    info_children: list = []
    if has_info and back is not None:
        info_children.append(StickerBridge(
            name="sticker", x=gx(back.x), y=gy(back.y),
            w=back.width, h=back.height, info=info))
    info_group = Group(name="Info", role="info", children=info_children)

    structure = Group(name="Structure", role="structure",
                      children=_structure_nodes(coords, gx, gy))

    root = Group(name="Artwork", role="artwork", children=[
        grounds, decoration, finishes, logo, typography, info_group, structure,
    ])
    doc = Document(
        page_w=vw, page_h=vh, title="BBROSE design (vector)",
        metadata={
            "typography_surface": "apps/ire/compose_vector_art.py::compose_vector_art_graph",  # §BH32(h)
            "has_info": has_info,
            "artwork_mode": NATIVE_VECTOR_RECONSTRUCTION,
            "concept_render_role": TEMPORARY_VISUAL_REFERENCE_ONLY,
            "style": language.name,
            "style_label": language.label,
            "swatches": params.swatches.to_dict(),
            "parameters": params.to_dict(),
            "panel_roles": surfaces,
            # 2A-6E-CORR-7: what the composition was built FROM — the
            # fidelity validator compares this against the selected concept.
            "concept_spec": concept_spec or None,
            "logo_zone_used": logo_zone_used,
            "finish_layers": (["SPOT_UV", "EMBOSS", "DEBOSS",
                               "ROSE_GOLD_FOIL"] if concept_spec else []),
            "confirmed_font": (concept_spec or {}).get("confirmed_font"),
            "extra_swatches": (["SOFT_MINT_WASH", "WHITE_TYPE_HIGHLIGHT"]
                               if concept_spec else []),
            "font_note": (
                "product typography is LIVE text in the emitter's embedded "
                "face; swap to the approved family in Illustrator — text "
                "remains editable"
            ),
        },
        root=root,
    )
    doc.metadata["inventory"] = document_inventory(doc, coords)
    return doc


# --- inventory ----------------------------------------------------------------


def document_inventory(doc: Document, coords=None) -> dict:
    """Raster/vector/text census — the editability evidence Gate 2 reads."""
    rasters: list[dict] = []
    counts = {"path": 0, "rect": 0, "text": 0, "image": 0, "barcode": 0,
              "group": 0, "sticker_bridge": 0, "asset_ref": 0}
    min_text_pt: float | None = None
    outlined_text = 0
    gradients = 0
    clip_masks = 0
    raster_area_mm2 = 0.0
    decorative_vector = 0
    panel_areas = []
    total_panel_area = 0.0
    if coords is not None:
        panel_areas = [(p.name, p.width * p.height) for p in coords.panels]
        total_panel_area = sum(a for _, a in panel_areas)

    for node, parent in doc.walk():
        counts[node.type] = counts.get(node.type, 0) + 1
        parent_role = getattr(parent, "role", "")
        if getattr(node, "clip", None):
            clip_masks += 1
        if isinstance(getattr(node, "fill", None), GradientFill):
            gradients += 1
        if node.type in ("path", "rect") and parent_role in (
                "decoration", "background", "effects", "product"):
            decorative_vector += 1
        if node.type == "text":
            min_text_pt = (node.size_pt if min_text_pt is None
                           else min(min_text_pt, node.size_pt))
            if getattr(node, "outline", False):
                outlined_text += 1
        if node.type == "image":
            area = node.w * node.h
            raster_area_mm2 += area
            panel_sized = any(area >= 0.25 * pa for _, pa in panel_areas)
            decorative = parent_role in ("background", "decoration",
                                         "product", "effects")
            rasters.append({
                "name": node.name,
                "src_basename": node.src.rsplit("/", 1)[-1],
                "w_mm": round(node.w, 2), "h_mm": round(node.h, 2),
                "parent_group": getattr(parent, "name", ""),
                "parent_role": parent_role,
                "panel_sized": panel_sized,
                "decorative": decorative,
                "logo_lockup": parent_role == "logo",
                "flag": BRAND_LOGO_RASTER_FALLBACK if parent_role == "logo" else "",
            })
    layer_groups = [
        {"name": g.name, "role": g.role, "children": len(g.children)}
        for g, _ in doc.walk() if isinstance(g, Group)
    ]
    return {
        "artwork_mode": doc.metadata.get("artwork_mode", ""),
        "node_counts": counts,
        "raster_count": len(rasters),
        "rasters": rasters,
        "decorative_raster_count": sum(1 for r in rasters if r["decorative"]),
        "panel_sized_raster_count": sum(1 for r in rasters if r["panel_sized"]),
        "raster_area_mm2": round(raster_area_mm2, 2),
        "raster_area_fraction": (round(raster_area_mm2 / total_panel_area, 5)
                                 if total_panel_area else 0.0),
        "decorative_vector_count": decorative_vector,
        "min_text_size_pt": min_text_pt,
        "vector_object_count": counts["path"] + counts["rect"] + counts["barcode"],
        "live_text_count": counts["text"],
        "outlined_text_count": outlined_text,
        "gradient_count": gradients,
        "clip_mask_count": clip_masks,
        "swatches": doc.metadata.get("swatches", {}),
        "layer_groups": layer_groups,
        "panel_roles": doc.metadata.get("panel_roles", []),
    }


# --- builders ------------------------------------------------------------------


def _bleed_ground(coords, params: LanguageParameters, gx, gy,
                  ivory_dominant: bool = False) -> Path:
    """One editable vertical gradient across the full bleed silhouette.

    ``ivory_dominant`` (2A-6E concept path): the base swatch carries ~3/4 of
    the sheet and the secondary appears only as a soft foot — the selected
    Powder Constellation ground is warm ivory with blush as an undertone,
    never a blush sheet."""
    ext = list(coords.bleed_polygon.exterior.coords)
    segs: list[Segment] = [MoveTo(x=gx(ext[0][0]), y=gy(ext[0][1]))]
    segs += [LineTo(x=gx(x), y=gy(y)) for x, y in ext[1:]]
    segs.append(ClosePath())
    min_x, min_y, max_x, max_y = coords.bleed_polygon.bounds
    top = params.swatches.ground_top.color()
    bottom = params.swatches.ground_bottom.color()
    stops = ([GradientStop(offset=0.0, color=top),
              GradientStop(offset=0.72, color=top),
              GradientStop(offset=1.0, color=bottom)]
             if ivory_dominant else
             [GradientStop(offset=0.0, color=top),
              GradientStop(offset=1.0, color=bottom)])
    return Path(
        name="ground-gradient", segments=segs,
        fill=GradientFill(
            kind="linear", stops=stops,
            x1=gx((min_x + max_x) / 2.0), y1=gy(min_y),
            x2=gx((min_x + max_x) / 2.0), y2=gy(max_y)),
    )


def _logo_nodes(front, logo_path, gx, gy, zone: str = "", logo_master=None) -> list:
    if logo_master is not None:
        # [the owner's second answer of 2026-09-25: the approved vector master — its ink bounds give the height]
        if front is None:
            return []
        ratio = logo_master.aspect
    else:
        if front is None or not logo_path or not os.path.exists(logo_path):
            return []
        from PIL import Image as PILImage
        with PILImage.open(logo_path) as im:
            lw, lh = im.size
        ratio = lh / lw if lw else 0.3
    zone_l = (zone or "").lower()
    if "upper left" in zone_l or "upper-left" in zone_l \
            or "top left" in zone_l or "top-left" in zone_l:
        # 2A-6E-CORR-7/8: the selected concept's logo zone is authoritative —
        # never re-centered, and sized with editorial authority (the
        # logo+frame group targets 32-45% of panel width).
        span = front.width * 0.34
        x = front.x + front.width * 0.08
    else:
        span = front.width * 0.60
        x = front.x + (front.width - span) / 2.0
    if logo_master is not None:
        from apps.ire import brand_mark
        return [brand_mark.mark_node(
            f"logo-front-{brand_mark.VECTOR_MASTER_FLAG}", logo_master,
            gx(x), gy(front.y + front.height * 0.14 - (0.06 * front.height if zone_l else 0.0)),
            span, span * ratio)]
    return [Image(
        name=f"logo-front-{BRAND_LOGO_RASTER_FALLBACK}", src=logo_path,
        x=gx(x), y=gy(front.y + front.height * 0.14 - (0.06 * front.height
                                                       if zone_l else 0.0)),
        w=span, h=span * ratio)]


def _concept_frame_nodes(front, spec, params, gx, gy) -> list:
    """The open rose-gold hairline frame adjacent to the logo (bottom and
    right sides, per the selected concept). Editable vector rules."""
    if front is None or not spec:
        return []
    zone = str(spec.get("logo_zone", "")).lower()
    if "frame" not in zone and "rectangle" not in zone:
        return []
    accent = params.swatches.accent.color()
    x0 = front.x + front.width * 0.07
    y0 = front.y + front.height * 0.055
    fw = front.width * 0.37
    fh = front.height * 0.16
    nodes = []
    for offset_index, offset in enumerate((0.0, 0.9)):   # double hairline
        nodes.append(Path(
            name=f"logo-frame-bottom-{offset_index}",
            segments=[MoveTo(x=gx(x0), y=gy(y0 + fh + offset)),
                      LineTo(x=gx(x0 + fw + offset), y=gy(y0 + fh + offset))],
            stroke=Stroke(color=accent, width_mm=0.25)))
        nodes.append(Path(
            name=f"logo-frame-right-{offset_index}",
            segments=[MoveTo(x=gx(x0 + fw + offset), y=gy(y0)),
                      LineTo(x=gx(x0 + fw + offset),
                             y=gy(y0 + fh + offset))],
            stroke=Stroke(color=accent, width_mm=0.25)))
    return nodes


def _concept_type_nodes(front, spec, params, gx, gy) -> list:
    """The selected concept's typography hierarchy as LIVE text
    (2A-6E-CORR-7): stacked product-name lines left-aligned to a one-third
    axis (line one in DUSTY_PINK_TYPE, line two in WHITE_TYPE_HIGHLIGHT),
    the tagline beneath, and the vertical Spanish product name on the right
    edge as a rotated live run. Never a small centered label."""
    from apps.ire.design_language import WHITE_TYPE_HIGHLIGHT

    if front is None or not spec:
        return []
    from apps.ire.text_metrics import (cap_height_em, resolve_metric_font,
                                       text_width_mm)

    nodes = []
    name_lines = [str(line)[:24] for line in (spec.get("name_lines") or [])
                  if line]
    left = front.x + front.width * 0.10
    # 2A-6E-CORR-10: the stacked name is sized from the ACTUAL registered
    # face's advances and cap height, so the emitted group lands inside the
    # contract bands (width 38-50% of panel, visual extent 42-58%) instead
    # of a placeholder guess. POWDER runs slightly smaller than BAKED (the
    # selected concept), and the inter-line air carries the constellation
    # flow between the words, exactly as image 89 does. The SAME resolution
    # the validator uses (confirmed face, else the registered placeholder
    # bold) keeps sizing, measurement and emission in agreement always.
    metric_font, metric_path = resolve_metric_font(
        {"confirmed_font": spec.get("confirmed_font")})
    cap_em = cap_height_em(metric_path)
    ratios = [1.0] + [0.85] * (len(name_lines) - 1)
    unit_widths = [ratio * text_width_mm(line, 1.0, metric_font)
                   for line, ratio in zip(name_lines, ratios)]
    widest = max(unit_widths) if unit_widths else 1.0
    size_1 = 0.46 * front.width / widest
    sizes = [size_1 * ratio for ratio in ratios]
    # visual extent: top of line-1 caps → baseline of the last line
    target_extent = 0.46 * front.height
    fixed = cap_em * sizes[0]
    gaps = max(1, len(name_lines) - 1)
    advance = max(1.15 * size_1,
                  (target_extent - fixed) / gaps) if name_lines else 0.0
    baseline = front.y + front.height * 0.24 + cap_em * sizes[0]
    line_colors = [params.swatches.line_deep.color(),
                   WHITE_TYPE_HIGHLIGHT.color(),
                   params.swatches.ink.color()]
    y = baseline
    for index, line in enumerate(name_lines):
        nodes.append(TextRun(
            name=f"product-name-line-{index + 1}", text=line,
            x=gx(left), y=gy(y), align="left",
            font="bold", size_pt=sizes[index] * 2.835,
            color=line_colors[min(index, len(line_colors) - 1)]))
        y += advance
    secondary = [s for s in (spec.get("secondary_copy") or []) if s]
    vertical = spec.get("vertical_copy")
    below = [s for s in secondary if s != vertical]
    if below:
        last_baseline = (baseline + (len(name_lines) - 1) * advance
                         if name_lines else front.y + front.height * 0.5)
        nodes.append(TextRun(
            name="tagline", text=below[0][:60],
            x=gx(left),
            y=gy(last_baseline + front.height * 0.055),
            align="left", font="regular",
            size_pt=max(_MIN_TEXT_PT, front.height * 2.835 * 0.032),
            color=params.swatches.ink.color()))
    if vertical:
        # anchored INSIDE the panel: rotated -90 with a left anchor runs
        # downward from y, so the whole run stays on the front face (the
        # first pass overflowed the panel top)
        nodes.append(TextRun(
            name="vertical-copy", text=vertical[:40],
            x=gx(front.x + front.width * 0.945),
            y=gy(front.y + front.height * 0.14),
            align="left", font="regular", rotation_deg=-90.0,
            size_pt=max(_MIN_TEXT_PT, front.height * 2.835 * 0.032),
            color=params.swatches.ink.color()))
    return nodes


def _concept_finish_layers(front, spec, params, name_nodes, gx, gy) -> list:
    """Separable finish layers (SPOT_UV / EMBOSS / DEBOSS / ROSE_GOLD_FOIL):
    named placeholder masks a finisher toggles or refines — never metallic
    effects baked into imagery."""
    if front is None or not spec:
        return []
    accent = params.swatches.accent.color()

    def _mask(name, x, y, w, h, layer):
        # a finish PLACEHOLDER is a labeled zone, not artwork: a thin dashed
        # outline the finisher refines — a painted fill polluted the visual
        # preview with tinted blocks over the logo/name/constellation
        return Rect(name=f"{layer}-{name}", x=gx(x), y=gy(y), w=w, h=h,
                    stroke=Stroke(color=accent, width_mm=0.2,
                                  dash=(1.2, 1.2), opacity=0.5))

    left = front.x + front.width * 0.10
    name_h = front.height * 0.115
    y = front.y + front.height * 0.34 - name_h * 0.8
    layers = {
        "SPOT_UV": [_mask("baked", left, y, front.width * 0.6, name_h,
                          "SPOT_UV")],
        "EMBOSS": [_mask("powder", left, y + name_h * 1.06,
                         front.width * 0.6, name_h, "EMBOSS"),
                   _mask("logo", front.x + front.width * 0.08,
                         front.y + front.height * 0.06,
                         front.width * 0.4, front.height * 0.10, "EMBOSS")],
        "DEBOSS": [],
        "ROSE_GOLD_FOIL": [
            _mask("frame", front.x + front.width * 0.07,
                  front.y + front.height * 0.06,
                  front.width * 0.47, front.height * 0.14,
                  "ROSE_GOLD_FOIL"),
            _mask("particles", front.x + front.width * 0.55,
                  front.y + front.height * 0.55,
                  front.width * 0.42, front.height * 0.42,
                  "ROSE_GOLD_FOIL")],
    }
    return [Group(name=layer_name, role="effects", children=children)
            for layer_name, children in layers.items()]


def _type_nodes(front, product_name, subtitle, params, gx, gy) -> list:
    if front is None:
        return []
    ink = params.swatches.ink.color()
    cx = front.x + front.width / 2.0
    nodes = []
    if product_name:
        nodes.append(TextRun(
            name="product-name", text=product_name[:40], x=gx(cx),
            y=gy(front.y + front.height * 0.56), align="center", font="bold",
            size_pt=max(9.0, front.width * 2.835 * 0.075), color=ink))
    if subtitle:
        nodes.append(TextRun(
            name="subtitle", text=subtitle[:60], x=gx(cx),
            y=gy(front.y + front.height * 0.63), align="center",
            font="regular",
            size_pt=max(_MIN_TEXT_PT, front.width * 2.835 * 0.045), color=ink))
    return nodes


__all__ = [
    "VectorArtStyle",
    "compose_vector_art_graph",
    "document_inventory",
    "NATIVE_VECTOR_RECONSTRUCTION",
    "TEMPORARY_VISUAL_REFERENCE_ONLY",
    "BRAND_LOGO_RASTER_FALLBACK",
    "VectorReconstructionReviewRequired",
    "LanguageParameters",
    "DEFAULT_EMPHASIS",
    "ROLE_FRONT",
]

# gen_gradient_field is part of the published primitive set (§7) and is
# exercised through the language library; referenced here so the standard
# ground primitive and the library ground stay the same code path.
_GROUND_PRIMITIVE = gen_gradient_field
