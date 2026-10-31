"""illustrator_handoff_graph/1.0 — the bounded reconstruction input
(Phase 2A-8 §9).

Serializes the canonical Design Graph into exactly the data a deterministic
Illustrator reconstruction needs: the mandated root-layer taxonomy, panel
sublayers, semantic groups, normalized path geometry, live text runs, named
process swatches, technical/finish spot swatches, masks, opacity,
printability and linked-asset identities. The Design Graph remains the
source of truth; this is an execution format, never a second design model.

Excluded by construction: prompts, provider payloads, credentials,
material-reference source paths, source-.ai vector paths, chain-of-thought,
unrelated task data, volatile timestamps.

Determinism (§10): traversal order fixes object order and generated IDs;
floats are rounded to 4 decimals; swatches sort by name; the canonical hash
is SHA-256 over the sorted-key JSON.
"""
from __future__ import annotations

import hashlib
import json
import os

from apps.ire import brand_mark as _brand_mark
from apps.ire.graph import (
    Barcode,
    ClosePath,
    CubicTo,
    Group,
    Image,
    LineTo,
    MoveTo,
    Path,
    Rect,
    SolidFill,
    StickerBridge,
    TextRun,
)

HANDOFF_SCHEMA = "illustrator_handoff_graph/1.0"

#: §3 root layers, in document order (top first in Illustrator's panel).
ROOT_LAYERS = (
    "00_REFERENCE_NONPRINTING",
    "01_DIELINE_CUT",
    "02_DIELINE_FOLD",
    "03_BLEED_SAFE_GUIDES",
    "14_TECHNICAL_NOTES",
    "10_FINISH_SPOT_UV",
    "11_FINISH_EMBOSS",
    "12_FINISH_DEBOSS",
    "13_FINISH_FOIL",
    "09_BARCODE_QR_BATCH",
    "08_REGULATORY_COPY",
    "07_LIVE_TYPOGRAPHY",
    "06_BRAND",
    "05_PANEL_ARTWORK",
    "04_BASE_COLORS",
)
PANEL_SUBLAYERS = ("FRONT", "BACK", "SIDE_LEFT", "SIDE_RIGHT", "TOP_FLAPS",
                   "BOTTOM_FLAPS", "DUST_FLAPS", "GLUE_FLAP")
NON_PRINTING_LAYERS = frozenset(
    {"00_REFERENCE_NONPRINTING", "03_BLEED_SAFE_GUIDES",
     "14_TECHNICAL_NOTES"})

#: §5 technical + finish SPOT swatches: (name, tint hex for screen, CMYK).
SPOT_SWATCHES = (
    # [his second goal of 2026-10-06, item 2] the die plates' own colours, as every other file draws them: the knife
    # magenta (the production PDF's CutContour), the creasing rules cyan (its Crease) — it was red and blue here
    ("CUT", "#EC008C", (0.0, 1.0, 0.0, 0.0)),
    ("CREASE", "#00AEEF", (1.0, 0.0, 0.0, 0.0)),
    ("SPOT_UV", "#00A0A0", (0.8, 0.0, 0.3, 0.0)),
    ("EMBOSS", "#808000", (0.2, 0.2, 1.0, 0.1)),
    ("DEBOSS", "#606060", (0.0, 0.0, 0.0, 0.7)),
    ("ROSE_GOLD_FOIL", "#B76E79", (0.12, 0.62, 0.42, 0.12)),
)
_FINISH_LAYER = {"SPOT_UV": "10_FINISH_SPOT_UV",
                 "EMBOSS": "11_FINISH_EMBOSS",
                 "DEBOSS": "12_FINISH_DEBOSS",
                 "ROSE_GOLD_FOIL": "13_FINISH_FOIL"}
_ROLE_TO_PANEL = {"front": "FRONT", "back": "BACK", "side_left": "SIDE_LEFT",
                  "side_right": "SIDE_RIGHT", "top_flap": "TOP_FLAPS",
                  "bottom_flap": "BOTTOM_FLAPS", "dust_flap": "DUST_FLAPS",
                  "glue_flap": "GLUE_FLAP"}


def _r(value: float) -> float:
    return round(float(value), 4)


def _segments(segments) -> list:
    out = []
    for seg in segments or []:
        if isinstance(seg, MoveTo):
            out.append(["M", _r(seg.x), _r(seg.y)])
        elif isinstance(seg, LineTo):
            out.append(["L", _r(seg.x), _r(seg.y)])
        elif isinstance(seg, CubicTo):
            out.append(["C", _r(seg.x1), _r(seg.y1), _r(seg.x2), _r(seg.y2),
                        _r(seg.x), _r(seg.y)])
        elif isinstance(seg, ClosePath):
            out.append(["Z"])
    return out


class _SwatchRegistry:
    """hex → stable swatch name; graph-known names win, unknown colors get
    deterministic COLOR_<HEX> names — never 'copy'/'-1' duplicates."""

    def __init__(self, named: dict):
        self._by_hex: dict = {}
        self._defs: dict = {}
        for name in sorted(named):
            entry = named[name]
            hex_value = str(entry.get("hex", "")).upper()
            self._by_hex.setdefault(hex_value, name)
            self._defs[name] = {"name": name, "hex": hex_value,
                                "cmyk": [_r(c) for c in entry.get("cmyk", [])],
                                "kind": "process"}

    def resolve(self, color) -> str:
        if color is None:
            return ""
        hex_value = "#%02X%02X%02X" % (round(color.r * 255),
                                       round(color.g * 255),
                                       round(color.b * 255))
        name = self._by_hex.get(hex_value)
        if name is None:
            name = f"COLOR_{hex_value[1:]}"
            self._by_hex[hex_value] = name
            cmyk = list(color.cmyk) if color.cmyk else [0.0, 0.0, 0.0, 0.0]
            self._defs[name] = {"name": name, "hex": hex_value,
                                "cmyk": [_r(c) for c in cmyk],
                                "kind": "process"}
        return name

    def definitions(self) -> list:
        return [self._defs[k] for k in sorted(self._defs)]


def _fill_record(fill, swatches: _SwatchRegistry):
    if fill is None:
        return None
    if isinstance(fill, SolidFill):
        return {"type": "solid", "swatch": swatches.resolve(fill.color),
                "opacity": _r(fill.opacity)}
    return {"type": "gradient", "kind": fill.kind,
            "stops": [{"offset": _r(s.offset),
                       "swatch": swatches.resolve(s.color),
                       "opacity": _r(s.opacity)} for s in fill.stops],
            "x1": _r(fill.x1), "y1": _r(fill.y1),
            "x2": _r(fill.x2), "y2": _r(fill.y2),
            "cx": _r(fill.cx), "cy": _r(fill.cy), "r": _r(fill.r)}


def _stroke_record(stroke, swatches: _SwatchRegistry):
    if stroke is None:
        return None
    return {"swatch": swatches.resolve(stroke.color),
            "width_mm": _r(stroke.width_mm),
            "dash": [_r(d) for d in stroke.dash] if stroke.dash else None,
            "opacity": _r(stroke.opacity)}


def _semantic_group_name(raw: str) -> str:
    """Deterministic bounded names — never anonymous 'Group N'."""
    name = (raw or "").strip()
    return name if name else "unnamed-group"


#: [E5b, the clean-up of 2026-10-04] the decoration group a carton's front is drawn in from its concept's map
#: (apps/ire/compose.py, compose_components_graph): every part in it is the FRONT panel's, whatever its inner
#: groups are named ("motif-map-front" read as a side's)
MAP_FRONT_GROUP = "Map front"


def _leaves(node) -> list:
    """A semantic group's leaves, in document order — [E5b] a group nested deeper (a carton front's map drawing:
    the parts within its outline, under the parts it runs edge to edge) opened, never emitted as an empty group
    record with its parts dropped. A leaf is itself."""
    if not isinstance(node, Group):
        return [node]
    out: list = []
    for child in node.children:
        out.extend(_leaves(child) if isinstance(child, Group) else [child])
    return out


def _panel_named_last(name: str) -> str:
    """[E5b] The panel a part drawn straight on a carton's panel names after its last index —
    "continued-band-0-side_left" -> SIDE_LEFT, "continued-rule-0-glue_tab" -> GLUE_FLAP; FRONT where it names
    none."""
    import re

    from apps.ire.design_language import panel_role
    found = re.match(r".*-\d+-(.+)$", name)
    return _ROLE_TO_PANEL.get(panel_role(found.group(1)), "FRONT") if found else "FRONT"


def serialize_handoff_graph(doc, *, task_id: int | None = None) -> dict:
    """The bounded illustrator_handoff_graph/1.0 for a composed Document."""
    metadata = doc.metadata or {}
    named_swatches = dict(metadata.get("swatches") or {})
    # the composer's extra named swatches (mint wash, type highlight)
    from apps.ire.design_language import SOFT_MINT_WASH, WHITE_TYPE_HIGHLIGHT
    for extra in (SOFT_MINT_WASH, WHITE_TYPE_HIGHLIGHT):
        named_swatches.setdefault(
            extra.name, {"hex": extra.hex, "cmyk": list(extra.cmyk)})
    swatches = _SwatchRegistry(named_swatches)

    confirmed_font = metadata.get("confirmed_font") or {}
    objects: list = []
    counter = {"n": 0}

    def _next_id(prefix: str) -> str:
        counter["n"] += 1
        return f"{prefix}-{counter['n']:04d}"

    def _emit(node, layer, panel, group_path, *, printable=True,
              finish="", clip=None):
        # THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo
        # trace, switch the mark to it so gold foil can print." A mark drawn from its approved vector master is
        # handed off as the ONE path it draws (apps/ire/brand_mark.py), its fill rule with it — never as an
        # AssetRef the script has no way to draw
        if _brand_mark.is_mark(node):
            node = _brand_mark.expanded(node)
        base = {
            "id": _next_id(node.type),
            "name": _semantic_group_name(getattr(node, "name", "")),
            "type": node.type,
            "layer": layer,
            "panel": panel,
            "group_path": list(group_path),
            "printable": bool(printable),
            "visible": True,
            "locked": layer in ("01_DIELINE_CUT", "02_DIELINE_FOLD"),
            "finish": finish,
            "opacity": _r(getattr(node, "opacity", 1.0)),
        }
        if isinstance(node, Path):
            base.update(segments=_segments(node.segments),
                        fill=_fill_record(node.fill, swatches),
                        stroke=_stroke_record(node.stroke, swatches))
            if node.fill_rule is not None:
                # [the owner's second answer of 2026-09-25: carried only when set, so every other path's record is
                # what it was; the script draws such a path as ONE compound path (jsx_emitter)]
                base["fill_rule"] = node.fill_rule
        elif isinstance(node, Rect):
            base.update(x=_r(node.x), y=_r(node.y), w=_r(node.w),
                        h=_r(node.h), radius_mm=_r(node.radius_mm),
                        fill=_fill_record(node.fill, swatches),
                        stroke=_stroke_record(node.stroke, swatches))
        elif isinstance(node, TextRun):
            base.update(text=node.text, x=_r(node.x), y=_r(node.y),
                        size_pt=_r(node.size_pt), align=node.align,
                        rotation_deg=_r(getattr(node, "rotation_deg", 0.0)),
                        font_role=node.font,
                        font_postscript=(confirmed_font.get("name")
                                         if node.font == "bold"
                                         and confirmed_font.get("name")
                                         else "NotoSans-Regular"
                                         if node.font == "regular"
                                         else "NotoSans-Bold"),
                        swatch=swatches.resolve(node.color),
                        live=True)
        elif isinstance(node, Image):
            base.update(x=_r(node.x), y=_r(node.y), w=_r(node.w),
                        h=_r(node.h),
                        linked_asset=os.path.basename(node.src or ""),
                        raster=True)
        elif isinstance(node, Barcode):
            base.update(symbology=node.symbology, x=_r(node.x), y=_r(node.y))
        elif isinstance(node, StickerBridge):
            base.update(x=_r(node.x), y=_r(node.y), w=_r(node.w),
                        h=_r(node.h), bridge=True,
                        note="trilingual regulatory sticker — rendered by "
                             "the proven legacy renderer in the preview; "
                             "native node port pending")
        if clip:
            base["clip"] = _segments(clip)
        objects.append(base)

    def _panel_of(group_name: str) -> str:
        from apps.ire.design_language import panel_role
        if "-" in group_name:
            surface = group_name.split("-", 1)[1]
            return _ROLE_TO_PANEL.get(panel_role(surface), "FRONT")
        return "FRONT"

    clips: list = []
    root = doc.root
    for top in root.children:
        role = getattr(top, "role", "generic")
        name = str(getattr(top, "name", ""))
        if role == "background":
            for child in top.children:
                if str(getattr(child, "name", "")) == "ground-gradient":
                    _emit(child, "04_BASE_COLORS", "", ["pastel-ground"])
                    # §3: a non-printing duplicate of the bleed silhouette
                    # doubles as the bleed guide
                    guide = Path(name="bleed-guide",
                                 segments=child.segments,
                                 stroke=child.stroke)
                    _emit(guide, "03_BLEED_SAFE_GUIDES", "",
                          ["bleed-safe-guides"], printable=False)
                else:
                    _emit(child, "04_BASE_COLORS", "", ["pastel-ground"])
        elif role == "decoration":
            for panel_group in top.children:
                group_name = str(getattr(panel_group, "name", ""))
                if not isinstance(panel_group, Group):
                    # [E5b] a part drawn straight on a carton's panel, named for it (a front's band continued
                    # round the carton) — it was dropped from the package
                    panel = _panel_named_last(group_name)
                    _emit(panel_group, "05_PANEL_ARTWORK", panel,
                          [f"{panel.lower()}-artwork", _semantic_group_name(name)])
                    continue
                panel = "FRONT" if name == MAP_FRONT_GROUP else _panel_of(group_name)
                clip = getattr(panel_group, "clip", None)
                wrapper = f"{panel.lower()}-artwork"
                if clip:
                    clips.append({"layer": "05_PANEL_ARTWORK",
                                  "panel": panel,
                                  "group_path": [wrapper],
                                  "segments": _segments(clip)})
                for semantic in getattr(panel_group, "children", []):
                    semantic_name = _semantic_group_name(
                        getattr(semantic, "name", ""))
                    if panel != "FRONT" and semantic_name.startswith(
                            "constellation"):
                        semantic_name = "panel-continuation"
                    for leaf in _leaves(semantic):
                        _emit(leaf, "05_PANEL_ARTWORK", panel,
                              [wrapper, semantic_name])
        elif role == "effects":
            for child in top.children:
                child_name = str(getattr(child, "name", ""))
                if isinstance(child, Group):
                    finish = child_name  # SPOT_UV / EMBOSS / DEBOSS / FOIL
                    layer = _FINISH_LAYER.get(finish, "14_TECHNICAL_NOTES")
                    for mask in child.children:
                        mask_name = str(getattr(mask, "name", "")) \
                            .replace("-", "_").upper()
                        mask = mask.model_copy(update={"name": mask_name})
                        _emit(mask, layer, "FRONT", [finish], finish=finish)
                elif child_name.startswith("logo-frame"):
                    _emit(child, "05_PANEL_ARTWORK", "FRONT",
                          ["FRONT", "logo-frame"])
                else:
                    _emit(child, "05_PANEL_ARTWORK", "FRONT",
                          ["FRONT", "accents"])
        elif role == "logo":
            for child in top.children:
                _emit(child, "06_BRAND", "FRONT", ["brand-logo"])
        elif role == "typography":
            for child in top.children:
                child_name = str(getattr(child, "name", ""))
                semantic = ("product-name"
                            if child_name.startswith("product-name")
                            else "secondary-copy")
                _emit(child, "07_LIVE_TYPOGRAPHY", "FRONT", [semantic])
        elif role == "info":
            for child in top.children:
                _emit(child, "08_REGULATORY_COPY", "BACK",
                      ["regulatory-sticker"])
        elif role == "structure":
            for child in top.children:
                child_name = str(getattr(child, "name", ""))
                if child_name.startswith("cut-halo") or \
                        child_name.startswith("fold-halo"):
                    _emit(child, "00_REFERENCE_NONPRINTING", "",
                          ["readability-halos"], printable=False)
                elif child_name == "cut" or child_name.startswith("slit-"):     # [his final goal, B2]
                    _emit(child, "01_DIELINE_CUT", "", ["cut"])
                    objects[-1]["stroke"]["swatch"] = "CUT"
                    objects[-1]["stroke"]["spot"] = True
                elif child_name.startswith("fold"):
                    _emit(child, "02_DIELINE_FOLD", "", ["fold"])
                    objects[-1]["stroke"]["swatch"] = "CREASE"
                    objects[-1]["stroke"]["spot"] = True
                else:
                    _emit(child, "14_TECHNICAL_NOTES", "",
                          ["technical"], printable=False)
        else:
            for child in getattr(top, "children", []):
                _emit(child, "14_TECHNICAL_NOTES", "",
                      [name or "unassigned"], printable=False)

    layer_tree: dict = {layer: {} for layer in ROOT_LAYERS}
    census: dict = {}
    for record in objects:
        layer = record["layer"]
        group_key = "/".join(record["group_path"]) or "(layer)"
        layer_tree.setdefault(layer, {})
        layer_tree[layer].setdefault(group_key, 0)
        layer_tree[layer][group_key] += 1
        census[record["type"]] = census.get(record["type"], 0) + 1

    graph = {
        "schema_version": HANDOFF_SCHEMA,
        "task_id": task_id,
        "artboard": {"w_mm": _r(doc.page_w), "h_mm": _r(doc.page_h)},
        "color_mode": "CMYK",
        "title": doc.title,
        "root_layers": list(ROOT_LAYERS),
        "panel_sublayers": list(PANEL_SUBLAYERS),
        "non_printing_layers": sorted(NON_PRINTING_LAYERS),
        "process_swatches": swatches.definitions(),
        "spot_swatches": [{"name": n, "hex": h, "cmyk": list(c),
                           "kind": "spot"} for n, h, c in SPOT_SWATCHES],
        "fonts": sorted({record["font_postscript"]
                         for record in objects
                         if record["type"] == "text"}),
        "objects": objects,
        "panel_clips": clips,
        # §6 design-review state: technical + finish layers ship hidden but
        # named/selectable; toggling them on is the documented prepress state
        "default_hidden_layers": ["00_REFERENCE_NONPRINTING",
                                  "01_DIELINE_CUT", "02_DIELINE_FOLD",
                                  "03_BLEED_SAFE_GUIDES",
                                  "14_TECHNICAL_NOTES",
                                  "10_FINISH_SPOT_UV", "11_FINISH_EMBOSS",
                                  "12_FINISH_DEBOSS", "13_FINISH_FOIL"],
        "layer_tree": layer_tree,
        "object_census": census,
        "finish_note": ("finish layers are SPOT-color production masks; "
                        "final overprint and separation settings require "
                        "prepress review"),
    }
    return graph


def canonical_hash(graph: dict) -> str:
    """SHA-256 over the sorted-key canonical JSON (no volatile fields)."""
    payload = json.dumps(graph, sort_keys=True, ensure_ascii=True,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def expected_layer_tree(graph: dict) -> dict:
    """The validator's expectation: layer → group → object count."""
    return {layer: dict(groups)
            for layer, groups in graph["layer_tree"].items()}


__all__ = ["serialize_handoff_graph", "canonical_hash",
           "expected_layer_tree", "HANDOFF_SCHEMA", "ROOT_LAYERS",
           "PANEL_SUBLAYERS", "NON_PRINTING_LAYERS", "SPOT_SWATCHES"]
