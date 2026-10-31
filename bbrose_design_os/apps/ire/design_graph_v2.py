"""Design Graph 2.0 — semantic components with provenance
(``container_design_graph/2.0``).

WHAT "GRAPH" MEANS TODAY, established before designing this, because v2
extends a LIVE contract rather than replacing one:

* ``apps.ire.graph.Document`` — the renderable node tree (Path, Rect,
  TextRun, Image, Barcode, AssetRef, Group). Geometry and content.
* ``container_design_graph/1.1`` — a CENSUS over that Document
  (``compose_container.container_design_graph_record``): how many live
  text runs, how many vector paths, how many rasters of each permitted
  class. It counts primitives; it does not say what any of them ARE.
* ``palette_design_graph/2.0`` — the palette arc's graph, which already
  solved provenance: every projected node records the intent field that
  drove it, its constraint level, its confirmation state and its
  confidence. That shape is ADOPTED here rather than reinvented.

WHAT v2 ADDS: the semantic layer between the two. A COMPONENT is a named
part of the product — a label panel, a closure, a logo placement — with
its own bounds and, mandatorily, its provenance.

A COMPONENT WITHOUT RECORDED PROVENANCE IS NOT A COMPONENT. There is no
"unknown origin" component class, and no branch that fabricates one: a
component whose provenance cannot be stated RAISES. AI never generates
geometry, so every component traces to a confirmed intent field, a
structural backbone, or an owner-supplied asset — and says which.

ADDITIVE BY CONSTRUCTION. ``visual_quality_gate._silhouette_axis`` reads
two keys off the graph record — ``reconstruction_silhouette`` (R2b's
measured comparison) and ``product_bounds`` (the structural fallback) —
and v2 must break neither. v2 carries the v1.1 census forward verbatim
and adds to it; a test asserts both gate paths still resolve from a v2
record.

Pure: no Django ORM, no provider calls, no network.
"""
from __future__ import annotations

SCHEMA = "container_design_graph/2.0"
EXTENDS = "container_design_graph/1.1"

#: Where a component is allowed to come from. There is deliberately no
#: "GENERATED" or "UNKNOWN" origin — AI never generates geometry, so an
#: origin that cannot be named is a refusal, not a category.
ORIGIN_CONFIRMED_INTENT = "CONFIRMED_INTENT_FIELD"
ORIGIN_STRUCTURAL_BACKBONE = "STRUCTURAL_BACKBONE"
ORIGIN_OWNER_ASSET = "OWNER_SUPPLIED_ASSET"
ORIGIN_DERIVED_LAYOUT = "DERIVED_FROM_CONFIRMED_LAYOUT"
ORIGINS = (ORIGIN_CONFIRMED_INTENT, ORIGIN_STRUCTURAL_BACKBONE,
           ORIGIN_OWNER_ASSET, ORIGIN_DERIVED_LAYOUT)

#: Semantic roles a component may claim. Closed set: a role outside it is
#: a refusal rather than a free-text label nobody can query.
ROLE_CONTAINER_BODY = "CONTAINER_BODY"
ROLE_CLOSURE = "CLOSURE"
ROLE_LABEL_PANEL = "LABEL_PANEL"
ROLE_LOGO = "LOGO"
ROLE_PRODUCT_NAME = "PRODUCT_NAME"
ROLE_MOTIF = "MOTIF"
ROLE_REFERENCE = "REFERENCE"
ROLES = (ROLE_CONTAINER_BODY, ROLE_CLOSURE, ROLE_LABEL_PANEL, ROLE_LOGO,
         ROLE_PRODUCT_NAME, ROLE_MOTIF, ROLE_REFERENCE)

#: Provenance fields every component must carry. Mirrors the palette
#: arc's _provenance shape so the two graphs stay readable together.
PROVENANCE_REQUIRED = ("origin", "source", "confirmation_state")

DG2_COMPONENT_WITHOUT_PROVENANCE = "DG2_COMPONENT_WITHOUT_PROVENANCE"
DG2_PROVENANCE_FIELD_MISSING = "DG2_PROVENANCE_FIELD_MISSING"
DG2_ORIGIN_INVALID = "DG2_ORIGIN_INVALID"
DG2_ROLE_INVALID = "DG2_ROLE_INVALID"
DG2_BASE_RECORD_INVALID = "DG2_BASE_RECORD_INVALID"
DG2_GATE_KEY_DROPPED = "DG2_GATE_KEY_DROPPED"
DG2_BOUNDS_INVALID = "DG2_BOUNDS_INVALID"

#: keys visual_quality_gate reads off the graph record. v2 is additive and
#: a v2 build that dropped one would silently un-measure an axis, so the
#: builder refuses rather than returning a record the gate reads as absent.
GATE_READ_KEYS = ("product_bounds", "reconstruction_silhouette",
                  "closure_assembly")


class DesignGraphV2Error(ValueError):
    """Fail-closed graph refusal; ``findings`` lists exact codes."""

    def __init__(self, findings):
        self.findings = list(findings)
        super().__init__("; ".join(self.findings))


def validate_provenance(provenance, *, component_id: str) -> dict:
    """A component's provenance, or a refusal. Never a default."""
    if not isinstance(provenance, dict) or not provenance:
        raise DesignGraphV2Error([
            f"{DG2_COMPONENT_WITHOUT_PROVENANCE}:{component_id}"])
    findings = [f"{DG2_PROVENANCE_FIELD_MISSING}:{component_id}:{f}"
                for f in PROVENANCE_REQUIRED if not provenance.get(f)]
    if findings:
        raise DesignGraphV2Error(findings)
    if provenance["origin"] not in ORIGINS:
        raise DesignGraphV2Error([
            f"{DG2_ORIGIN_INVALID}:{component_id}:{provenance['origin']}"])
    return {f: provenance[f] for f in PROVENANCE_REQUIRED} | {
        k: v for k, v in provenance.items() if k not in PROVENANCE_REQUIRED}


def _validate_bounds(bounds, *, component_id: str):
    """Bounds are optional — many components genuinely have none recorded
    yet — but a bounds key that IS present must be real."""
    if bounds is None:
        return None
    if not isinstance(bounds, dict) or not {"width_mm", "height_mm"} <= set(
            bounds):
        raise DesignGraphV2Error([
            f"{DG2_BOUNDS_INVALID}:{component_id}:expected width_mm and "
            "height_mm"])
    for key in ("width_mm", "height_mm"):
        value = bounds[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool) \
                or value <= 0:
            raise DesignGraphV2Error([
                f"{DG2_BOUNDS_INVALID}:{component_id}:{key}={value!r}"])
    return {"width_mm": float(bounds["width_mm"]),
            "height_mm": float(bounds["height_mm"])}


def component(component_id: str, *, role: str, provenance: dict,
              node_names=(), bounds_mm=None, constraints=()) -> dict:
    """Build one semantic component. Raises unless its provenance can be
    stated — there is no unknown-origin component."""
    if role not in ROLES:
        raise DesignGraphV2Error([f"{DG2_ROLE_INVALID}:{component_id}:"
                                  f"{role}"])
    return {
        "component_id": component_id,
        "role": role,
        "node_names": list(node_names),
        "bounds_mm": _validate_bounds(bounds_mm, component_id=component_id),
        "constraints": list(constraints),
        "provenance": validate_provenance(provenance,
                                          component_id=component_id),
    }


def components_from_document(doc, *, backbone_source: str = "") -> list:
    """Derive components from an emitted Document, naming provenance for
    each rather than inferring one.

    Only nodes whose semantic role is EVIDENT from the composer's own
    naming become components. A node that cannot be classified is left
    out rather than guessed into a role — an unclassified primitive stays
    a primitive in the v1.1 census, which is honest, whereas a guessed
    component would be a claim.

    VQR-3: ``bounds_mm`` is fed from the node's OWN emitted box wherever the
    node states one. An Image carries w/h in document mm, so its bounds are
    read, not derived. A Group states no box — measuring one means unioning a
    subtree whose text extents need font metrics nothing here has — so group
    bounds stay absent rather than becoming an estimate.
    """
    from apps.ire.brand_mark import is_mark as _is_mark
    found = []
    for node, parent in doc.walk():
        name = str(getattr(node, "name", "") or "")
        low = name.lower()
        role = None
        origin = ORIGIN_DERIVED_LAYOUT
        if node.type == "image" and (
                "reference" in low
                or (parent and getattr(parent, "name", "") == "Reference")):
            role, origin = ROLE_REFERENCE, ORIGIN_OWNER_ASSET
        elif node.type == "image" and "logo" in low:
            role, origin = ROLE_LOGO, ORIGIN_OWNER_ASSET
        elif _is_mark(node) and "logo" in low:
            # [the owner's second answer of 2026-09-25: the mark drawn from its approved vector master — the owner's
            # asset, its box its own (apps/ire/brand_mark.py)]
            role, origin = ROLE_LOGO, ORIGIN_OWNER_ASSET
        elif node.type == "group" and low.startswith("motif-"):
            role, origin = ROLE_MOTIF, ORIGIN_CONFIRMED_INTENT
        elif node.type == "group" and name.startswith("Surface-"):
            role, origin = ROLE_LABEL_PANEL, ORIGIN_DERIVED_LAYOUT
        if role is None:
            continue
        bounds = None
        width, height = getattr(node, "w", None), getattr(node, "h", None)
        if isinstance(width, (int, float)) and isinstance(height, (int, float)) \
                and not isinstance(width, bool) and not isinstance(height, bool) \
                and width > 0 and height > 0:
            bounds = {"width_mm": round(width, 3),
                      "height_mm": round(height, 3)}
        provenance = {
            "origin": origin,
            "source": (backbone_source if origin ==
                       ORIGIN_STRUCTURAL_BACKBONE else
                       f"composer node {name!r}"),
            "confirmation_state": "EMITTED_BY_COMPOSER",
            "derived_by": "design_graph_v2.components_from_document",
        }
        if bounds is not None:
            # _validate_bounds keeps only width/height, so where the numbers
            # came from is recorded here instead of being silently dropped
            provenance["bounds_measured_from"] = "emitted image node box"
        found.append(component(
            name or f"{node.type}-unnamed", role=role,
            node_names=[name], bounds_mm=bounds, provenance=provenance))
    return found


def build(base_record: dict, *, components=(), constraints=()) -> dict:
    """Extend a ``container_design_graph/1.1`` record into a 2.0 record.

    ADDITIVE: every key of the base record survives verbatim. The keys
    ``visual_quality_gate`` reads are checked explicitly after the merge,
    because dropping one would not raise anywhere else — it would just
    make an axis quietly UNMEASURED again.
    """
    if not isinstance(base_record, dict) or not base_record.get(
            "schema_version", "").startswith("container_design_graph/"):
        raise DesignGraphV2Error([
            f"{DG2_BASE_RECORD_INVALID}:"
            f"{(base_record or {}).get('schema_version')}"])

    validated = []
    for comp in components:
        # re-validate even pre-built components: a caller may hand-assemble
        # a dict, and provenance is not optional at any entry point
        validated.append(component(
            comp["component_id"], role=comp["role"],
            provenance=comp.get("provenance"),
            node_names=comp.get("node_names", ()),
            bounds_mm=comp.get("bounds_mm"),
            constraints=comp.get("constraints", ())))

    record = dict(base_record)
    record["schema_version"] = SCHEMA
    record["extends"] = base_record.get("schema_version", EXTENDS)
    record["census"] = {k: v for k, v in base_record.items()
                        if k not in ("schema_version",)}
    record["components"] = validated
    record["component_roles"] = sorted({c["role"] for c in validated})
    record["constraints"] = list(constraints)
    record["provenance_rule"] = (
        "a component without recorded provenance is not a component; there "
        "is no unknown-origin class and AI never generates geometry")

    dropped = [k for k in GATE_READ_KEYS
               if k in base_record and k not in record]
    if dropped:
        raise DesignGraphV2Error(
            [f"{DG2_GATE_KEY_DROPPED}:{k}" for k in dropped])
    return record
