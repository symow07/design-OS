"""Product Container native Illustrator handoff (Phase 2B-4A/B).

Extends the validated 2A-8 packaging handoff engine through a target-specific
adapter — the canonical source is the container Document composed from the
persisted ``container_design_graph/1.1`` chain, and the JSX stays a pure
execution format re-using the shared data-driven runtime.

The human visual authority travels with the package: a rejected output emits a
TECHNICAL HANDOFF — HUMAN VISUAL REJECTION ACTIVE label, and no execution or
layer-tree success can clear it.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path as FsPath

from apps.ire import brand_mark as _brand_mark
from apps.ire.graph import Color, Image, Path, Rect, TextRun
from apps.ire.handoff.graph_schema import (
    _fill_record,
    _r,
    _segments,
    _semantic_group_name,
    _stroke_record,
    _SwatchRegistry,
)
from apps.ire.handoff.jsx_emitter import EMITTER_VERSION
from apps.pipeline.services.container_contract import zone_surface

CONTAINER_HANDOFF_SCHEMA = "container_illustrator_handoff_graph/1.0"
CONTAINER_MANIFEST_SCHEMA = "container_illustrator_handoff_manifest/1.0"

HUMAN_REJECTION_LABEL = "TECHNICAL HANDOFF — HUMAN VISUAL REJECTION ACTIVE"

#: §3 deterministic root-layer ORDER (only applicable layers are emitted).
CONTAINER_ROOT_LAYER_ORDER = (
    "00_REFERENCE_NONPRINTING", "01_CONTAINER_PROFILE", "02_DECORATION_ZONES",
    "03_BASE_CONTAINER", "04_PRODUCT_FILL", "05_FRONT_ARTWORK",
    "06_BACK_ARTWORK", "07_SIDE_WRAP_ARTWORK", "08_CAP_ARTWORK",
    "09_LIVE_TYPOGRAPHY", "10_BRAND", "11_LABEL_TECHNICAL",
    "12_PROCESS_ARTWORK", "13_WHITE_UNDERBASE", "14_SCREEN_INKS",
    "15_PAD_PRINT", "16_HOT_STAMP", "17_SPOT_UV", "18_EMBOSS", "19_DEBOSS",
    "20_BOTTOM_CODE", "21_SEAM_AND_REGISTRATION", "22_TECHNICAL_NOTES",
)

_NON_PRINTING = ("00_REFERENCE_NONPRINTING", "01_CONTAINER_PROFILE",
                 "02_DECORATION_ZONES", "21_SEAM_AND_REGISTRATION",
                 "22_TECHNICAL_NOTES")

#: §11 concept-review opening state — hidden by default.
_DEFAULT_HIDDEN = ("00_REFERENCE_NONPRINTING", "01_CONTAINER_PROFILE",
                   "02_DECORATION_ZONES", "11_LABEL_TECHNICAL",
                   "13_WHITE_UNDERBASE", "14_SCREEN_INKS", "15_PAD_PRINT",
                   "16_HOT_STAMP", "17_SPOT_UV", "18_EMBOSS", "19_DEBOSS",
                   "20_BOTTOM_CODE", "21_SEAM_AND_REGISTRATION",
                   "22_TECHNICAL_NOTES")

#: surface → the artwork root layer its panel artwork lives on (§4).
_SURFACE_LAYER = {
    "BODY_FRONT": "05_FRONT_ARTWORK", "BODY_BACK": "06_BACK_ARTWORK",
    "BODY_LEFT": "07_SIDE_WRAP_ARTWORK", "BODY_RIGHT": "07_SIDE_WRAP_ARTWORK",
    "BODY_WRAP": "07_SIDE_WRAP_ARTWORK", "SHOULDER": "07_SIDE_WRAP_ARTWORK",
    "NECK": "07_SIDE_WRAP_ARTWORK", "CAP_FRONT": "08_CAP_ARTWORK",
    "CAP_BACK": "08_CAP_ARTWORK", "CAP_TOP": "08_CAP_ARTWORK",
    "CAP_WRAP": "08_CAP_ARTWORK", "BOTTOM": "20_BOTTOM_CODE",
    "CRIMP_ZONE": "20_BOTTOM_CODE",
}

#: separation → the finish/plate layer that represents it (§11).
_SEPARATION_LAYER = {
    "WHITE_UNDERBASE": "13_WHITE_UNDERBASE", "SCREEN_INK_1": "14_SCREEN_INKS",
    "SCREEN_INK_2": "14_SCREEN_INKS", "PAD_PRINT_INK_1": "15_PAD_PRINT",
    "HOT_STAMP_FOIL": "16_HOT_STAMP", "CAP_FOIL": "16_HOT_STAMP",
    "SPOT_UV": "17_SPOT_UV", "EMBOSS": "18_EMBOSS", "DEBOSS": "19_DEBOSS",
    "BOTTOM_CODE": "20_BOTTOM_CODE", "LABEL_CUT": "11_LABEL_TECHNICAL",
    "LABEL_BLEED": "11_LABEL_TECHNICAL", "LABEL_SAFE": "11_LABEL_TECHNICAL",
    "SHRINK_SLEEVE_SEAM": "21_SEAM_AND_REGISTRATION",
}


def serialize_container_handoff_graph(doc, spec: dict, *,
                                      task_id: int | None = None) -> dict:
    """container_illustrator_handoff_graph/1.0 for a composed container
    Document + its persisted spec records. Deterministic; no provider."""
    metadata = doc.metadata or {}
    swatches = _SwatchRegistry(dict(metadata.get("swatches") or {}))
    objects: list = []
    counter = {"n": 0}
    surfaces_present: set[str] = set()

    def _next_id(prefix: str) -> str:
        counter["n"] += 1
        return f"{prefix}-{counter['n']:04d}"

    def _emit(node, layer, surface, group_path, *, printable=True,
              visible=True, finish=""):
        # THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo
        # trace, switch the mark to it so gold foil can print." A mark drawn from its approved vector master is
        # handed off as the ONE path it draws (apps/ire/brand_mark.py), its fill rule with it
        if _brand_mark.is_mark(node):
            node = _brand_mark.expanded(node)
        base = {
            "id": _next_id(node.type),
            "name": _semantic_group_name(getattr(node, "name", "")),
            "type": node.type, "layer": layer, "panel": surface,
            "group_path": list(group_path), "printable": bool(printable),
            "visible": bool(visible), "locked": layer in (
                "01_CONTAINER_PROFILE", "02_DECORATION_ZONES"),
            "finish": finish, "opacity": _r(getattr(node, "opacity", 1.0)),
        }
        if isinstance(node, Path):
            base.update(segments=_segments(node.segments),
                        fill=_fill_record(node.fill, swatches),
                        stroke=_stroke_record(node.stroke, swatches))
            if node.fill_rule is not None:
                # [the owner's second answer of 2026-09-25: carried only when set; the script draws such a path as
                # ONE compound path (jsx_emitter), so the mark's counters stay holes]
                base["fill_rule"] = node.fill_rule
        elif isinstance(node, Rect):
            base.update(x=_r(node.x), y=_r(node.y), w=_r(node.w),
                        h=_r(node.h), radius_mm=_r(node.radius_mm),
                        fill=_fill_record(node.fill, swatches),
                        stroke=_stroke_record(node.stroke, swatches))
        elif isinstance(node, TextRun):
            fonts_rec = spec.get("container_font_authority/1.0") or {}
            faces = {f.get("role"): f for f in fonts_rec.get("faces") or []}
            face = faces.get(node.font) or {}
            base.update(text=node.text, x=_r(node.x), y=_r(node.y),
                        size_pt=_r(node.size_pt), align=node.align,
                        rotation_deg=_r(getattr(node, "rotation_deg", 0.0)),
                        font_role=node.font,
                        font_postscript=face.get("postscript_name")
                        or _theme_ps(node.font),      # §BH32(e) W7
                        swatch=swatches.resolve(node.color), live=True)
        elif isinstance(node, Image):
            base.update(x=_r(node.x), y=_r(node.y), w=_r(node.w),
                        h=_r(node.h),
                        linked_asset=os.path.basename(node.src or ""),
                        raster=True)
        objects.append(base)
        if surface:
            surfaces_present.add(surface)

    def _walk(group, layer, surface, path):
        for child in getattr(group, "children", []) or []:
            cname = str(getattr(child, "name", ""))
            if getattr(child, "type", "") == "group":
                _walk(child, layer, surface, path + [cname])
            elif child.type == "text":
                _emit(child, "09_LIVE_TYPOGRAPHY", surface,
                      path + ["live-type"])
            elif (child.type == "image" or _brand_mark.is_mark(child)) and "logo" in cname:
                # [the owner's second answer of 2026-09-25: the mark drawn from its approved vector master is the
                # brand too]
                _emit(child, "10_BRAND", surface, path + ["logo"])
            else:
                _emit(child, layer, surface, path)

    # --- walk the composed document into container layers -------------------
    for top in (doc.root.children or []):
        tname = str(getattr(top, "name", ""))
        if tname == "Reference":
            _walk(top, "00_REFERENCE_NONPRINTING", "", ["reference"])
        elif tname == "Container":
            for child in top.children:
                cname = str(getattr(child, "name", ""))
                if cname in ("product-peach-rose-fill", "glass-highlight"):
                    _emit(child, "04_PRODUCT_FILL", "BODY_FRONT",
                          ["product-fill"])
                elif cname in ("body", "body-transparent-wall", "cap",
                               "silhouette-outline"):
                    _emit(child, "03_BASE_CONTAINER", "",
                          ["container-wall" if "body" in cname else cname])
                elif getattr(child, "type", "") == "group":
                    _walk(child, "05_FRONT_ARTWORK", "BODY_FRONT",
                          ["front-decoration"])
                elif child.type == "text":
                    _emit(child, "09_LIVE_TYPOGRAPHY", "BODY_FRONT",
                          ["live-type"])
                elif child.type == "image" or _brand_mark.is_mark(child):
                    # [the owner's second answer of 2026-09-25: a mark drawn from its approved vector master sits
                    # where the raster sat — without this branch it matched none above and was dropped]
                    _emit(child, "10_BRAND", "BODY_FRONT", ["logo"])
        elif tname == "Surfaces":
            for panel in top.children:
                pname = str(getattr(panel, "name", ""))
                surface = pname.upper()
                for prefix in ("SURFACE-", "PANEL-"):
                    if surface.startswith(prefix):
                        surface = surface[len(prefix):]
                layer = _SURFACE_LAYER.get(surface, "07_SIDE_WRAP_ARTWORK")
                _walk(panel, layer, surface, [pname])
        elif tname == "Spec":
            _walk(top, "22_TECHNICAL_NOTES", "", ["spec"])
        else:
            _walk(top, "22_TECHNICAL_NOTES", "", [tname or "misc"])

    # --- 01 container profile + 02 decoration zones (technical, §6) ---------
    profile = spec.get("container_profile/1.0") or {}
    zones_rec = spec.get("container_decoration_zones/1.0") or {}
    fields = profile.get("fields") or {}

    def _tech_text(name, text, y, layer):
        _emit(TextRun(name=name, text=text[:180], x=14, y=y, size_pt=5,
                      color=Color.from_hex("#555555"), font="regular",
                      align="left"),
              layer, "", ["technical"], printable=False, visible=False)

    y = 30.0
    for label, value in (
            ("archetype", profile.get("archetype")),
            ("variant", profile.get("variant")),
            ("body_mm", "%s × %s × %s" % (
                (fields.get("body_width_mm") or {}).get("value"),
                (fields.get("body_depth_mm") or {}).get("value"),
                (fields.get("body_height_mm") or {}).get("value"))),
            ("cap_mm", "%s × %s × %s (unconfirmed dims omitted)" % (
                (fields.get("cap_width_mm") or {}).get("value"),
                (fields.get("cap_depth_mm") or {}).get("value"),
                (fields.get("cap_height_mm") or {}).get("value"))),
            ("neck_ratio", (fields.get("neck_ratio") or {}).get("value")),
            ("cross_section", str((fields.get("base_geometry") or {})
                                  .get("value"))[:60]),
            ("body_opacity", (fields.get("body_opacity") or {}).get("value")),
            ("front_orientation", str((fields.get("front_orientation") or {})
                                      .get("value"))[:60]),
            ("profile_hash", profile.get("profile_hash")),
            ("zone_set_hash", zones_rec.get("zone_set_hash")),
            ("combined_hash", (spec.get("container_confirmation") or {})
             .get("combined_hash")),
            ("authority", "inferred manufacturer tolerances are NOT verified "
                          "geometry")):
        _tech_text(f"profile-{label}", f"{label}: {value}", y,
                   "01_CONTAINER_PROFILE")
        y += 6
    for z in zones_rec.get("zones") or []:
        _emit(Rect(name=f"zone-{z.get('zone_id')}", x=float(z.get("x") or 0),
                   y=float(z.get("y") or 0), w=float(z.get("width") or 1),
                   h=float(z.get("height") or 1)),
              "02_DECORATION_ZONES", zone_surface(z) or "",
              ["zones"], printable=False, visible=False)

    # --- separations as independently selectable plate layers (§11) ---------
    separations = (spec.get("container_production_separations/1.0")
                   or {}).get("separations") or []
    sep_names: list[str] = []
    sy = 40.0
    seen_seps: set = set()
    separation_inventory: list = []
    for sep in separations:
        name = str(sep.get("name") or "")
        layer = _SEPARATION_LAYER.get(name)
        if name == "PROCESS_ARTWORK" or layer is None or name in seen_seps:
            continue                     # process artwork IS the visible art
        seen_seps.add(name)
        sep_names.append(name)
        separation_inventory.append({
            "name": name, "layer": layer,
            "method": sep.get("method_type") or sep.get("method_id", ""),
            "classification": str(sep.get("classification") or "").upper(),
            "printable": bool(sep.get("printable", True)),
            "overprint": sep.get("overprint", ""),
            "visibility_default": sep.get("visibility_default", "hidden"),
            "zones": sep.get("zones") or sep.get("target_zones") or [],
            "surfaces": sep.get("surfaces") or sep.get("target_surfaces") or [],
        })
        _tech_text(f"separation-{name.lower()}",
                   f"{name}: method={sep.get('method_type')} "
                   f"zones={sep.get('zones') or sep.get('target_zones')} "
                   f"class={sep.get('classification') or sep.get('kind')} "
                   "(plate placeholder — geometry masks require prepress)",
                   sy, layer)
        sy += 6

    # --- assemble ------------------------------------------------------------
    layers_used = {o["layer"] for o in objects}
    root_layers = [name for name in CONTAINER_ROOT_LAYER_ORDER
                   if name in layers_used]
    panel_map: dict[str, list] = {}
    for o in objects:
        if o["panel"] and o["layer"] in (
                "05_FRONT_ARTWORK", "06_BACK_ARTWORK", "07_SIDE_WRAP_ARTWORK",
                "08_CAP_ARTWORK", "20_BOTTOM_CODE"):
            panel_map.setdefault(o["layer"], [])
            if o["panel"] not in panel_map[o["layer"]]:
                panel_map[o["layer"]].append(o["panel"])
    for names in panel_map.values():
        names.sort()

    layer_tree: dict = {layer: {} for layer in root_layers}
    census: dict = {}
    for o in objects:
        census[o["type"]] = census.get(o["type"], 0) + 1
        key = "/".join(o["group_path"]) or "(layer)"
        layer_tree[o["layer"]].setdefault(key, 0)
        layer_tree[o["layer"]][key] += 1

    # §1 canonical classification: the persisted record's ``classification``
    # (case-insensitive) is the ONE contract — never inferred from the name,
    # never a container-only lowercase reinterpretation (the defect that
    # reported spot_count=0 while SPOT separations existed).
    sep_record = spec.get("container_production_separations/1.0") or {}
    registry = sep_record.get("swatches") or []

    def _classify(entry) -> str:
        return str(entry.get("classification") or entry.get("kind")
                   or "").upper()

    def _swatch_row(entry):
        return {"name": str(entry.get("name")),
                "hex": entry.get("hex") or "#888888",
                "cmyk": entry.get("cmyk") or [0, 0, 0, 0.5],
                "classification": _classify(entry),
                "overprint": entry.get("overprint", ""),
                "value": entry.get("value", ""),
                "note": ("TECHNICAL_PLACEHOLDER — unverified"
                         if entry.get("value") == "TECHNICAL_PLACEHOLDER"
                         else "")}

    spot_swatches = [_swatch_row(e) for e in registry
                     if _classify(e) == "SPOT"]
    technical_swatches = [_swatch_row(e) for e in registry
                          if _classify(e) == "TECHNICAL"]

    fonts_rec = spec.get("container_font_authority/1.0") or {}
    fonts = sorted({f.get("postscript_name") for f in
                    (fonts_rec.get("faces") or []) if f.get("postscript_name")}
                   or {_theme_ps("regular"), _theme_ps("bold")})   # §BH32(e) W7

    graph = {
        "schema_version": CONTAINER_HANDOFF_SCHEMA,
        "emitter_version": EMITTER_VERSION,
        "task_id": task_id,
        "artboard": {"w_mm": _r(doc.page_w), "h_mm": _r(doc.page_h)},
        "title": doc.title,
        "root_layers": root_layers,
        "panel_sublayers": sorted(surfaces_present),
        "panel_sublayer_map": panel_map,
        "non_printing_layers": sorted(set(_NON_PRINTING) & layers_used),
        "default_hidden_layers": [n for n in _DEFAULT_HIDDEN
                                  if n in layers_used],
        "process_swatches": swatches.definitions(),
        "spot_swatches": spot_swatches,
        "technical_swatches": technical_swatches,
        "separation_inventory": separation_inventory,
        "fonts": fonts,
        "objects": objects,
        "object_census": census,
        "layer_tree": layer_tree,
        "separations_included": sep_names,
        "finish_note": ("plate/finish layers are placeholders bound to the "
                        "persisted separations manifest; final overprint and "
                        "separation settings require prepress review"),
    }
    return graph


def canonical_container_hash(graph: dict) -> str:
    core = {k: v for k, v in graph.items() if k not in ("emitter_version",)}
    return hashlib.sha256(json.dumps(
        core, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True).encode()).hexdigest()


def validate_container_handoff(doc, graph: dict, spec: dict) -> list[str]:
    """Structural validation codes for the container handoff (2B-4C)."""
    codes: list[str] = []
    if graph.get("schema_version") != CONTAINER_HANDOFF_SCHEMA:
        codes.append("HANDOFF_SCHEMA_MISMATCH")
    zones = (spec.get("container_decoration_zones/1.0") or {}).get("zones") or []
    expected_surfaces = {zone_surface(z) for z in zones if zone_surface(z)}
    archetype = (spec.get("container_profile/1.0") or {}).get("archetype", "")
    if archetype == "bottle" and any(
            "CRIMP" in (s or "") for s in graph.get("panel_sublayers", [])):
        codes.append("HANDOFF_CRIMP_ON_RIGID_CONTAINER")
    missing = expected_surfaces - set(graph.get("panel_sublayers") or []) \
        - {"BODY_FRONT"}                # the hero front may render on Container
    front_present = any(o["layer"] == "05_FRONT_ARTWORK"
                        for o in graph["objects"])
    if "BODY_FRONT" in expected_surfaces and not front_present:
        codes.append("HANDOFF_FRONT_ARTWORK_MISSING")
    if missing:
        codes.append("HANDOFF_SURFACE_MISSING: " + ",".join(sorted(missing)))
    decorative_rasters = [o for o in graph["objects"]
                          if o.get("raster") and o["layer"] not in
                          ("00_REFERENCE_NONPRINTING", "10_BRAND")]
    if decorative_rasters:
        codes.append("HANDOFF_DECORATIVE_RASTER_PRESENT")
    if not any(o["type"] == "text" and o.get("live")
               and o["layer"] == "09_LIVE_TYPOGRAPHY"
               for o in graph["objects"]):
        codes.append("HANDOFF_LIVE_TEXT_MISSING")
    dupes = {s["name"] for s in graph["spot_swatches"]
             if any(s["name"].endswith(suf) for suf in (" copy", "-1", " 2"))}
    if dupes:
        codes.append("HANDOFF_DUPLICATE_SWATCH_NAMES")
    # §3 cross-record consistency: separations ↔ spot swatches ↔ census.
    spot_names = [s["name"] for s in graph["spot_swatches"]]
    if len(spot_names) != len(set(spot_names)):
        codes.append("HANDOFF_DUPLICATE_SPOT_SWATCH")
    inventory = graph.get("separation_inventory", [])
    spot_set = set(spot_names)
    used: set = set()
    for sep in inventory:
        if sep.get("classification") == "SPOT" and sep.get("printable"):
            if sep["name"] not in spot_set:
                codes.append(f"HANDOFF_SPOT_COLOR_MISSING: {sep['name']}")
            else:
                used.add(sep["name"])
        elif sep.get("classification") == "PROCESS" \
                and sep["name"] in spot_set:
            codes.append(
                f"HANDOFF_SEPARATION_SWATCH_MISMATCH: {sep['name']} is "
                "PROCESS but registered as a spot swatch")
    orphans = spot_set - used
    if orphans:
        codes.append("HANDOFF_ORPHAN_SPOT_SWATCH: "
                     + ",".join(sorted(orphans)))
    # census invariant: counts must equal inventory lengths
    if len(inventory) != len(graph.get("separations_included", [])):
        codes.append("HANDOFF_MANIFEST_CENSUS_INACCURATE: separations")
    if inventory and any(s.get("classification") == "SPOT"
                         for s in inventory) and not spot_names:
        codes.append("HANDOFF_MANIFEST_CENSUS_INACCURATE: spot_count zero "
                     "while SPOT separations exist")
    return codes


def build_container_handoff_package(doc, spec: dict, out_dir: str, *,
                                    task_id: int,
                                    human_acceptance: dict,
                                    readiness_codes: list,
                                    logo_asset: str | None = None) -> dict:
    """Write the container package; return {graph, manifest, paths, hashes}."""
    import shutil

    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.handoff.jsx_emitter import emit_design_handoff_jsx

    out = FsPath(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    linked: list[str] = []
    if logo_asset and FsPath(logo_asset).exists():
        assets = out / "assets"
        assets.mkdir(exist_ok=True)
        shutil.copyfile(logo_asset, assets / FsPath(logo_asset).name)
        linked.append(FsPath(logo_asset).name)

    graph = serialize_container_handoff_graph(doc, spec, task_id=task_id)
    graph_hash = canonical_container_hash(graph)
    jsx = emit_design_handoff_jsx(graph)
    jsx_hash = hashlib.sha256(jsx.encode()).hexdigest()
    (out / "design_graph.json").write_text(
        json.dumps(graph, indent=1, ensure_ascii=True))
    (out / "design_handoff.jsx").write_text(jsx)

    # per-surface artwork PDFs (§2): the composed document is re-emitted per
    # surface family from its groups — never concept-sheet screenshots.
    emit_pdf_ai(doc, str(out / "concept_sheet_preview.pdf"))
    seps = spec.get("container_production_separations/1.0") or {}
    (out / "production_separations_manifest.json").write_text(
        json.dumps(seps, indent=1, ensure_ascii=True))

    tree_hash = hashlib.sha256(json.dumps(
        graph["layer_tree"], sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()

    rejected = "REJECTED" in str(human_acceptance.get("state", ""))
    manifest = {
        "schema_version": CONTAINER_MANIFEST_SCHEMA,
        "handoff_graph_schema": CONTAINER_HANDOFF_SCHEMA,
        "emitter_version": EMITTER_VERSION,
        "task_id": task_id,
        "target": "product_container",
        "selected_variation_identity":
            (spec.get("container_selected_variation/1.0") or {}
             ).get("variation_id", ""),
        "container_profile_hash":
            (spec.get("container_profile/1.0") or {}).get("profile_hash", ""),
        "zone_set_hash": (spec.get("container_decoration_zones/1.0") or {}
                          ).get("zone_set_hash", ""),
        "combined_confirmation_hash":
            (spec.get("container_confirmation") or {}).get("combined_hash", ""),
        "design_graph_hash": graph_hash,
        "motif_hash": (spec.get("container_motif_spec/1.0") or {}
                       ).get("motif_hash", ""),
        "wrap_set_hash": (spec.get("container_wrap_geometry/1.0") or {}
                          ).get("wrap_set_hash", ""),
        "method_set_hash": (spec.get("container_production_method/1.0") or {}
                            ).get("method_set_hash", ""),
        "separation_set_hash": seps.get("separation_set_hash", ""),
        "jsx_hash": jsx_hash,
        "layer_tree_hash": tree_hash,
        "fonts": graph["fonts"],
        "font_authority": _bounded_font_authority(spec),
        "font_policy": "font references only — no binaries ship",
        "process_swatches": [s["name"] for s in graph["process_swatches"]],
        "spot_swatches": [s["name"] for s in graph["spot_swatches"]],
        "technical_swatches": [s["name"] for s in
                               graph.get("technical_swatches", [])],
        "separation_inventory": graph.get("separation_inventory", []),
        # §2 census: every count equals the length of its inventory list —
        # validated by validate_container_handoff (census invariant).
        "process_swatch_count": len(graph["process_swatches"]),
        "spot_swatch_count": len(graph["spot_swatches"]),
        "technical_swatch_count": len(graph.get("technical_swatches", [])),
        "separation_count": len(graph.get("separation_inventory", [])),
        "printable_separation_count": sum(
            1 for x in graph.get("separation_inventory", [])
            if x.get("printable")),
        "nonprinting_technical_count": sum(
            1 for x in graph.get("separation_inventory", [])
            if not x.get("printable")),
        "finish_separation_count": sum(
            1 for x in graph.get("separation_inventory", [])
            if x.get("layer") in ("13_WHITE_UNDERBASE", "16_HOT_STAMP",
                                  "17_SPOT_UV", "18_EMBOSS", "19_DEBOSS")),
        "expected_object_census": graph["object_census"],
        "expected_layer_tree": graph["layer_tree"],
        "live_text_count": graph["object_census"].get("text", 0),
        "raster_fallback_count": graph["object_census"].get("image", 0),
        "decorative_raster_count": 0,
        "surface_inventory": graph["panel_sublayers"],
        "zone_inventory": [z.get("zone_id") for z in
                           (spec.get("container_decoration_zones/1.0") or {}
                            ).get("zones") or []],
        "separations_included": graph["separations_included"],
        "production_readiness_codes": list(readiness_codes),
        "human_visual_acceptance_state": human_acceptance.get("state", ""),
        "production_blockers": list(human_acceptance.get("codes") or []),
        "handoff_label": (HUMAN_REJECTION_LABEL if rejected
                          else "TECHNICAL HANDOFF"),
        "production_ready": False,
        "execution_verification":
            "ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED",
        "linked_assets": sorted(linked),
        "notes": graph["finish_note"],
    }
    (out / "handoff_manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=True))
    return {"graph": graph, "manifest": manifest,
            "paths": {"jsx": str(out / "design_handoff.jsx"),
                      "graph": str(out / "design_graph.json"),
                      "manifest": str(out / "handoff_manifest.json")},
            "hashes": {"graph": graph_hash, "jsx": jsx_hash,
                       "layer_tree": tree_hash}}


def _theme_ps(role: str) -> str:
    """§BH32(e) W7: the fallback name when the record carries none — the
    theme's face for the role through the layer (bold → display, regular →
    body), never a literal."""
    from apps.ire.font_roles import base_role, theme_postscript
    return theme_postscript(base_role(role or "regular"),
                            "NotoSans-Bold" if role == "bold" else "NotoSans-Regular")


def _bounded_font_authority(spec: dict) -> list[dict]:
    faces = (spec.get("container_font_authority/1.0") or {}).get("faces") or []
    return [{k: f.get(k) for k in (
        "family", "style", "postscript_name", "sha256", "licence_state",
        "authority", "embedding_state", "finding")} for f in faces]


__all__ = [
    "CONTAINER_HANDOFF_SCHEMA", "CONTAINER_MANIFEST_SCHEMA",
    "CONTAINER_ROOT_LAYER_ORDER", "HUMAN_REJECTION_LABEL",
    "serialize_container_handoff_graph", "canonical_container_hash",
    "validate_container_handoff", "build_container_handoff_package",
]
