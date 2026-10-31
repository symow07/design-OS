"""PALT-M4C §7 — the ES3083 Design Graph.

The Design Graph is the contract between design reasoning and production.
This module projects a CONFIRMED palette intent plus its built geometry
onto it, so the palette becomes an artifact the rest of the pipeline can
read rather than a mesh with a description beside it.

Four rules are enforced rather than documented.

* **Provenance.** Every node records the intent field behind it. A node
  with no intent behind it is a fabrication.
* **Authority.** A DECORATIVE_PREFERENCE can never drive a structure
  node, so §H's finding that the bubble scatter is ornament and not
  moulded relief is a rule.
* **Honest geometry state.** The graph carries the lid, base, hinge and
  clasp because the design has them — and marks them
  ``NOT_BUILT``, because PALT-M4B-B has not been built. A node that
  claimed built geometry it does not have would be worse than a missing
  node.
* **Separation.** The ES3083 display box is LINKED as a Packaging
  artifact, never merged. Merging would let a carton dimension present
  itself as a palette dimension.

Pantone tokens are NODES, not colours. No licensed conversion exists
here, so the graph carries the name as the authority and a visibly
neutral placeholder for preview only.
"""
from __future__ import annotations

import hashlib
import json

from apps.ire.graph import Color, Document, Group, Rect, TextRun
from apps.pipeline.services import palette_design_intent as di

SCHEMA = "palette_design_graph/2.0"
GRAPH_VERSION = 2

UNRESOLVED_SPOT_PLACEHOLDER = Color(r=0.5, g=0.5, b=0.5)

SPOT_COLOUR_AUTHORITY = {
    "state": "UNRESOLVED_SPOT_COLOUR",
    "why": "Pantone 621 C / 627 C are named on the production sheet and "
           "confirmed by the owner, but no licensed Pantone conversion is "
           "available here. Inventing an RGB or CMYK value would create a "
           "colour nobody specified.",
    "governs": "THE_NAMED_SPOT_COLOUR_NOT_THE_PLACEHOLDER",
    "required_before_emission": "licensed spot definition or an owner-"
                                "supplied measured value",
}

ROLE_BY_LEVEL = {
    di.HARD: ("structure", "panel", "typography", "logo", "label", "info"),
    di.SOFT: ("panel", "typography", "logo", "label", "decoration", "info"),
    di.DECORATIVE: ("decoration",),
}

BUILT, NOT_BUILT = "BUILT", "NOT_BUILT"

#: Components the design has. Those without geometry say so.
COMPONENTS = (
    ("case", "the whole palette body", NOT_BUILT, "PALT-M4B-B"),
    ("lid", "the hinged upper half", NOT_BUILT, "PALT-M4B-B"),
    ("base", "the lower half carrying the tray", NOT_BUILT, "PALT-M4B-B"),
    ("tray", "the moulded recessed tray", BUILT, None),
    ("hinge", "the lid pivot", NOT_BUILT, "PALT-M4B-B"),
    ("clasp", "the closure catch", NOT_BUILT, "PALT-M4B-B"),
)

OPEN, CLOSED = "OPEN", "CLOSED"


def _identity(doc, packaging_link) -> str:
    """Canonical identity: key order must not change the hash, or a
    serialize/reconstruct round trip would look like an edit."""
    payload = json.dumps(
        {"document": json.loads(doc.model_dump_json()),
         "packaging_link": packaging_link},
        sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


class PaletteGraphError(ValueError):
    """Raised when a projection would exceed what the intent supports."""


def _provenance(field, role):
    allowed = ROLE_BY_LEVEL.get(field.constraint_level, ())
    if role not in allowed:
        raise PaletteGraphError(
            f"{field.name!r} is {field.constraint_level} and cannot drive a "
            f"{role!r} node — allowed roles are {list(allowed)}")
    return {"intent_field": field.name,
            "constraint_level": field.constraint_level,
            "confirmation_state": field.confirmation_state,
            "confidence": round(float(field.confidence), 3),
            "source_region": field.source_region,
            "graph_role": role}


def _require(intent, name):
    field = intent.get(name)
    if field is None:
        raise PaletteGraphError(
            f"the intent carries no {name!r} — the graph will not invent one")
    if field.confirmation_state == di.REMOVED:
        raise PaletteGraphError(f"{name!r} was removed by the owner")
    return field


def build_palette_design_graph(intent, tray, *, pan=None) -> dict:
    """Project a confirmed palette intent and its geometry onto a
    Document plus a relationship graph."""
    prov: list = []
    w = float(tray["spec"]["tray_width_mm"])
    h = float(tray["spec"]["tray_depth_mm"])
    g = tray["grid"]

    # --- structure: the pan field, from BUILT geometry ------------------
    shape_field = _require(intent, "pan_shapes")
    pan_nodes, pan_ids = [], []
    for p in tray["pockets"]:
        cx, cy = p["centre_mm"]
        pw, ph = p["opening_width_mm"], p["opening_height_mm"]
        nid = f"pan_r{p['row']}c{p['col']}"
        pan_ids.append(nid)
        pan_nodes.append(Rect(
            name=nid, x=w / 2 + cx - pw / 2, y=h / 2 + cy - ph / 2,
            w=pw, h=ph, radius_mm=p["sharp_corner_radius_at_deck_mm"]))
    prov.append(_provenance(shape_field, "structure"))
    structure = Group(name="pan_field", role="structure", children=pan_nodes)

    # --- typography, ordered by hierarchy -------------------------------
    type_field = _require(intent, "typography_zones")
    prov.append(_provenance(type_field, "typography"))
    runs, y, size = [], h - 8.0, 13.0
    for line in type_field.value:
        runs.append(TextRun(name=f"wordmark_{line.replace(' ', '_').lower()}",
                            text=line, x=w / 2, y=y, size_pt=size,
                            align="center",
                            color=UNRESOLVED_SPOT_PLACEHOLDER))
        y -= size * 0.62
        size = max(6.0, size - 2.0)
    typography = Group(name="wordmarks", role="typography", children=runs)

    # --- shade-label strips --------------------------------------------
    shade_field = intent.get("shade_names")
    labels = []
    if shade_field is not None and \
            shade_field.confirmation_state != di.REMOVED:
        prov.append(_provenance(shade_field, "label"))
        for p in tray["pockets"]:
            cx, cy = p["centre_mm"]
            labels.append(Rect(
                name=f"shade_label_r{p['row']}c{p['col']}",
                x=w / 2 + cx - p["opening_width_mm"] / 2,
                y=h / 2 + cy - p["opening_height_mm"] / 2 - 3.2,
                w=p["opening_width_mm"], h=2.8, radius_mm=0.4))
    shade_zone = Group(name="shade_label_strips", role="label",
                       children=labels)

    # --- decoration: ornament stays ornament ----------------------------
    decor = []
    for name in ("ornament", "pattern"):
        f = intent.get(name)
        if f is None or f.confirmation_state == di.REMOVED:
            continue
        prov.append(_provenance(f, "decoration"))
        decor.append(Group(name=f"{name}_{f.value}".lower(),
                           role="decoration"))
    decoration = Group(name="ornament", role="decoration", children=decor)

    # --- Pantone reference nodes: names, never converted -----------------
    colour_field = _require(intent, "colour_zones")
    prov.append(_provenance(colour_field, "panel"))
    named_colours = list(colour_field.value)
    colour_zone = Group(
        name="colour_zones", role="panel",
        children=[Rect(name=f"colour_zone_{t.replace(' ', '_')}",
                       x=4.0, y=h - 6.0 - i * 6.0, w=18.0, h=5.0,
                       radius_mm=0.8, fill=None)
                  for i, t in enumerate(named_colours)])

    artwork = Group(name="artwork_zones", role="artwork",
                    children=[typography, shade_zone, decoration,
                              colour_zone])
    root = Group(name="palette_artwork", role="artwork",
                 children=[structure, artwork])

    # --- relationships ---------------------------------------------------
    rels = []
    for r in range(g["rows"]):
        rels.append({"kind": "ROW_GROUP", "row": r,
                     "members": [n for n in pan_ids if n.startswith(f"pan_r{r}")],
                     "constraint": "ALIGNED_ON_Y"})
    for c in range(g["columns"]):
        rels.append({"kind": "COLUMN_GROUP", "column": c,
                     "members": [n for n in pan_ids if n.endswith(f"c{c}")],
                     "constraint": "ALIGNED_ON_X"})
    lx = round(g["pitch_x_mm"] - tray["pockets"][0]["opening_width_mm"], 6)
    ly = round(g["pitch_y_mm"] - tray["pockets"][0]["opening_height_mm"], 6)
    rels.append({"kind": "SPACING", "axis": "x", "land_mm": lx,
                 "pitch_mm": g["pitch_x_mm"]})
    rels.append({"kind": "SPACING", "axis": "y", "land_mm": ly,
                 "pitch_mm": g["pitch_y_mm"]})
    rels.append({"kind": "MARGIN", "border_mm": round(
        (w - g["columns"] * g["pitch_x_mm"]) / 2.0, 6),
        "rule": "border equals the inter-pocket land"})
    rels.append({"kind": "RELATIVE_SIZE", "rule": "ALL_PANS_EQUAL",
                 "members": pan_ids})
    rels.append({"kind": "ALIGNMENT", "rule": "ORTHOGONAL_GRID",
                 "rows": g["rows"], "columns": g["columns"]})
    for parent, child in (("case", "lid"), ("case", "base"),
                          ("base", "tray"), ("tray", "pan_field"),
                          ("lid", "hinge"), ("lid", "clasp")):
        rels.append({"kind": "PARENT_CHILD", "parent": parent,
                     "child": child})

    components = [{"id": cid, "means": means, "geometry_state": state,
                   "built_by": owner_slice,
                   "mesh_identity": tray["mesh_identity"]
                   if state == BUILT else None}
                  for cid, means, state, owner_slice in COMPONENTS]

    states = {
        OPEN: {"lid_angle_deg": 110.0, "visible": ["tray", "pan_field",
                                                   "shade_label_strips"],
               "geometry_state": NOT_BUILT},
        CLOSED: {"lid_angle_deg": 0.0,
                 "visible": ["case", "artwork_zones"],
                 "geometry_state": NOT_BUILT},
    }

    doc = Document(page_w=w, page_h=h,
                   title="BBROSE OUTER GLOW EYESHADOW PALETTE",
                   root=root,
                   metadata={
                       "schema": SCHEMA, "graph_version": GRAPH_VERSION,
                       "design_target": "palette",
                       "concept_reference": intent.concept_reference,
                       "intent_identity": intent.identity(),
                       "tray_mesh_identity": tray["mesh_identity"],
                       "pan_mesh_identity": (pan or {}).get("mesh_identity"),
                       "provenance": prov,
                       "named_colour_references": named_colours,
                       "spot_colour_authority": dict(SPOT_COLOUR_AUTHORITY),
                       "dimensional_authority":
                           dict(tray["dimensional_authority"]),
                       "components": components,
                       "relationships": rels,
                       "states": states,
                   })

    packaging_link = {
        "record_type": "palette_packaging_link/1.0",
        "relationship": "APPEARS_ON_THE_SAME_SOURCE_SHEET",
        "linked_target": "packaging",
        "artifact": "ES3083 display box (吸塑_展盒刀线)",
        "merged_into_palette": False,
        "why_not_merged": "the display box is a Packaging artifact with its "
                          "own dieline and its own structural authority. "
                          "Merging it would let a carton dimension present "
                          "itself as a palette dimension.",
        "shared_fields": [f.name for f in intent.fields
                          if f.artwork_relevance
                          and f.confirmation_state != di.REMOVED],
        "packaging_authority": "NOT_ESTABLISHED_BY_THIS_MODULE",
    }

    return {
        "record_type": SCHEMA,
        "graph_version": GRAPH_VERSION,
        "document": doc,
        "packaging_link": packaging_link,
        "graph_identity": _identity(doc, packaging_link),
        "node_count": sum(1 for _ in doc.walk()),
        "relationship_count": len(rels),
        "components": components,
        "unbuilt_components": [c["id"] for c in components
                               if c["geometry_state"] == NOT_BUILT],
        "unresolved": [
            "named spot colours are not resolved to licensed values",
            "lid, base, hinge and clasp geometry is NOT_BUILT (PALT-M4B-B)",
            "page size is the PROVISIONAL tray envelope, not a measured "
            "product dimension",
            *intent.unresolved_regions,
        ],
        "emission_ready": False,
        "why_not_emission_ready": "unresolved spot colours, provisional "
                                  "dimensions, and four unbuilt components",
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }


# --------------------------------------------------------------------------
# serialization, versioning, editing, reconstruction
# --------------------------------------------------------------------------

def serialize(graph) -> str:
    """Deterministic JSON for the whole graph."""
    doc = graph["document"]
    return json.dumps({
        "schema": SCHEMA, "graph_version": graph["graph_version"],
        "graph_identity": graph["graph_identity"],
        "document": json.loads(doc.model_dump_json()),
        "packaging_link": graph["packaging_link"],
    }, sort_keys=True, separators=(",", ":"))


def deserialize(blob: str) -> dict:
    """Rebuild a graph from its serialized form."""
    data = json.loads(blob)
    if data.get("schema") != SCHEMA:
        raise PaletteGraphError(
            f"cannot read graph schema {data.get('schema')!r}; this module "
            f"is {SCHEMA}")
    doc = Document.model_validate(data["document"])
    return {"record_type": SCHEMA,
            "graph_version": data["graph_version"],
            "document": doc,
            "packaging_link": data["packaging_link"],
            "graph_identity": _identity(doc, data["packaging_link"]),
            "node_count": sum(1 for _ in doc.walk()),
            "relationship_count": len(
                doc.metadata.get("relationships", [])),
            "components": doc.metadata.get("components", []),
            "owner_approved": False,
            "manufacturing_authority": "NOT_ESTABLISHED"}


def edit_text(graph, node_name: str, new_text: str) -> dict:
    """Edit one text run and return a NEW graph — the original is left
    alone so an edit is auditable rather than destructive."""
    blob = json.loads(serialize(graph))
    found = False
    def walk(node):
        nonlocal found
        if node.get("type") == "text" and node.get("name") == node_name:
            node["text"] = new_text
            found = True
        for child in node.get("children", []):
            walk(child)
    walk(blob["document"]["root"])
    if not found:
        raise PaletteGraphError(f"no text node named {node_name!r}")
    blob["graph_version"] = graph["graph_version"] + 1
    return deserialize(json.dumps(blob))
