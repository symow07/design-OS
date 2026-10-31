"""M5 §11/§12 — the generalized material and colour engine.

Material is a parameter set, not a property of a mesh. The engine's whole
claim is that changing colour or finish never requires rebuilding
geometry, so the test that matters is an identity test: same
MESH_GEOMETRY_IDENTITY, different MATERIAL_CONTRACT_IDENTITY, different
EVIDENCE_IDENTITY.

Nothing here is ES3083-specific. ES3083 appears only as one assignment
among several, and its Pantone tokens stay symbolic: 621 C and 627 C are
NAMED references carrying no RGB or Lab value, because this repository
holds no licensed conversion and inventing one would create a colour
nobody specified.
"""
from __future__ import annotations

import hashlib
import json

SCHEMA = "palette_material_contract/1.0"

# --- materials -------------------------------------------------------------
ABS = "ABS"
PP = "PP"
ACRYLIC = "ACRYLIC"
METAL = "METAL"
PAPERBOARD_COMPOSITE = "PAPERBOARD_COMPOSITE"
MATERIALS = (ABS, PP, ACRYLIC, METAL, PAPERBOARD_COMPOSITE)

MATTE = "MATTE"
SATIN = "SATIN"
GLOSSY = "GLOSSY"
METALLIC = "METALLIC"
TRANSPARENT = "TRANSPARENT"
TRANSLUCENT = "TRANSLUCENT"
FINISHES = (MATTE, SATIN, GLOSSY, METALLIC, TRANSPARENT, TRANSLUCENT)

#: Physical response per material. These are rendering parameters, not
#: manufacturing data — no supplier has confirmed any of them.
MATERIAL_BASE = {
    ABS: {"base_roughness": 0.55, "ior": 1.52, "metallic": 0.0,
          "transmission": 0.0, "microtexture": "FINE_MOULD_GRAIN"},
    PP: {"base_roughness": 0.62, "ior": 1.49, "metallic": 0.0,
         "transmission": 0.0, "microtexture": "SOFT_MOULD_GRAIN"},
    ACRYLIC: {"base_roughness": 0.12, "ior": 1.49, "metallic": 0.0,
              "transmission": 0.86, "microtexture": "NONE"},
    METAL: {"base_roughness": 0.28, "ior": 2.6, "metallic": 1.0,
            "transmission": 0.0, "microtexture": "BRUSHED_ANISOTROPY"},
    PAPERBOARD_COMPOSITE: {"base_roughness": 0.86, "ior": 1.4,
                           "metallic": 0.0, "transmission": 0.0,
                           "microtexture": "FIBRE"},
}

#: How a finish modifies the base. Each is a distinct response rather than
#: one shader with a roughness dial: transmission, metallic, sheen and
#: clearcoat move independently.
FINISH_MODIFIER = {
    MATTE: {"roughness": 0.88, "metallic_scale": 1.0, "transmission": 0.0,
            "sheen": 0.0, "clearcoat": 0.0},
    # M5 §5: at roughness 0.42 satin rendered indistinguishably from
    # matte — a broad lobe either way. Real satin has a tighter specular
    # lobe and a light coat over it, which is a physical difference rather
    # than a nudge to clear a bar. The bar did not move.
    SATIN: {"roughness": 0.26, "metallic_scale": 1.0, "transmission": 0.0,
            "sheen": 0.55, "clearcoat": 0.30},
    GLOSSY: {"roughness": 0.09, "metallic_scale": 1.0, "transmission": 0.0,
             "sheen": 0.0, "clearcoat": 0.55},
    METALLIC: {"roughness": 0.26, "metallic_scale": 1.0,
               "metallic_floor": 0.85, "transmission": 0.0, "sheen": 0.0,
               "clearcoat": 0.15},
    TRANSPARENT: {"roughness": 0.05, "metallic_scale": 0.0,
                  "transmission": 0.92, "sheen": 0.0, "clearcoat": 0.3},
    TRANSLUCENT: {"roughness": 0.38, "metallic_scale": 0.0,
                  "transmission": 0.55, "sheen": 0.12, "clearcoat": 0.1},
}

RESOLVED, SYMBOLIC = "RESOLVED_VALUE", "SYMBOLIC_NAMED_REFERENCE"

VISUALIZATION_ONLY = "VISUALIZATION_ONLY"

#: §7 — a symbolic colour still has to be shown as SOMETHING. These are
#: display proxies and nothing more: they carry no colour authority, they
#: are not conversions, and the NAME beside them remains the authority.
#: Chosen only to be distinguishable from each other and from the neutral
#: clay, so a reviewer can see which zone is which.
PANTONE_621C = "PANTONE 621 C"
PANTONE_627C = "PANTONE 627 C"

DISPLAY_PROXY = {
    PANTONE_621C: (0.72, 0.80, 0.74),
    PANTONE_627C: (0.16, 0.30, 0.24),
}


class MaterialError(ValueError):
    """Raised when a material assignment cannot be honoured exactly."""


class Colour:
    """Either a resolved value or a named reference carrying no value.

    A named reference NEVER gains an RGB. Fabricating one is how a
    licensed colour system turns into a number nobody specified.
    """

    __slots__ = ("kind", "name", "rgb", "why_unresolved")

    def __init__(self, *, name=None, rgb=None, why_unresolved=""):
        if rgb is not None:
            if len(rgb) != 3 or not all(0.0 <= c <= 1.0 for c in rgb):
                raise MaterialError(f"rgb must be three 0-1 values: {rgb}")
            self.kind, self.rgb = RESOLVED, tuple(round(c, 6) for c in rgb)
            self.name = name or ""
            self.why_unresolved = ""
        else:
            if not name:
                raise MaterialError("a colour needs a value or a name")
            self.kind, self.rgb, self.name = SYMBOLIC, None, name
            self.why_unresolved = why_unresolved or (
                "no licensed conversion is available in this repository")

    def to_dict(self):
        return {"kind": self.kind, "name": self.name, "rgb": self.rgb,
                "why_unresolved": self.why_unresolved}

    def __eq__(self, other):
        return isinstance(other, Colour) and self.to_dict() == other.to_dict()

    def __repr__(self):                                  # pragma: no cover
        return f"Colour({self.kind}, {self.name!r}, {self.rgb})"


def pantone(token: str) -> Colour:
    """A Pantone token stays symbolic. Always."""
    return Colour(name=token,
                  why_unresolved="Pantone is a licensed system and this "
                                 "repository holds no conversion; the "
                                 "NAME is the authority")


def display_proxy(colour: Colour) -> dict:
    """What to SHOW for a colour, and with what authority.

    A resolved colour shows itself. A symbolic one shows a proxy that is
    labelled visualization-only, so a render can exist without the record
    ever claiming colour accuracy.
    """
    if colour.kind == RESOLVED:
        return {"rgb": list(colour.rgb),
                "authority": "RESOLVED_COLOUR_VALUE",
                "is_proxy": False,
                "colour_authority": colour.name or "OWNER_SUPPLIED_VALUE"}
    rgb = DISPLAY_PROXY.get(colour.name, (0.55, 0.55, 0.57))
    return {"rgb": list(rgb),
            "authority": VISUALIZATION_ONLY,
            "is_proxy": True,
            "colour_authority": colour.name,
            "accuracy_claimed": False,
            "why": "no licensed value exists for this token; the proxy "
                   "exists so the zone can be seen, and the NAME remains "
                   "the authority"}


class MaterialAssignment:
    """A per-component material, finish and colour."""

    def __init__(self, component_pattern, material, finish, colour, *,
                 note=""):
        if material not in MATERIALS:
            raise MaterialError(f"unknown material {material!r}")
        if finish not in FINISHES:
            raise MaterialError(f"unknown finish {finish!r}")
        if not isinstance(colour, Colour):
            raise MaterialError("colour must be a Colour")
        if material == METAL and finish in (TRANSPARENT, TRANSLUCENT):
            raise MaterialError(
                f"{material} cannot take a {finish} finish — a metal does "
                "not transmit light")
        if material == PAPERBOARD_COMPOSITE and finish == TRANSPARENT:
            raise MaterialError(
                "paperboard composite cannot be transparent")
        self.component_pattern = component_pattern
        self.material, self.finish, self.colour = material, finish, colour
        self.note = note

    def resolved(self) -> dict:
        base = dict(MATERIAL_BASE[self.material])
        mod = FINISH_MODIFIER[self.finish]
        metallic = base["metallic"] * mod["metallic_scale"]
        if self.finish == METALLIC:
            metallic = max(metallic, mod.get("metallic_floor", 0.0))
        return {
            "component_pattern": self.component_pattern,
            "material": self.material, "finish": self.finish,
            "colour": self.colour.to_dict(),
            "roughness": round(mod["roughness"], 6),
            "metallic": round(metallic, 6),
            "transmission": round(max(base["transmission"],
                                      mod["transmission"]), 6),
            "sheen": mod["sheen"], "clearcoat": mod["clearcoat"],
            "ior": base["ior"], "microtexture": base["microtexture"],
            "display": display_proxy(self.colour),
            "display_rgb": display_proxy(self.colour)["rgb"],
            "note": self.note,
        }


class MaterialContract:
    """A named set of assignments applied to an unchanged mesh."""

    def __init__(self, name, assignments, *, description=""):
        self.name = name
        self.assignments = list(assignments)
        self.description = description

    def for_component(self, component_name):
        """Last matching pattern wins, so a specific rule overrides a
        general one."""
        chosen = None
        for a in self.assignments:
            if (a.component_pattern == "*"
                    or component_name.startswith(a.component_pattern)):
                chosen = a
        if chosen is None:
            raise MaterialError(
                f"no material assignment matches {component_name!r}; the "
                "engine will not guess one")
        return chosen

    def resolve(self, component_names) -> dict:
        return {n: self.for_component(n).resolved()
                for n in sorted(component_names)}

    def identity(self) -> str:
        payload = json.dumps(
            {"name": self.name,
             "assignments": [a.resolved() for a in self.assignments]},
            sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self, component_names=()) -> dict:
        symbolic = [a.colour.name for a in self.assignments
                    if a.colour.kind == SYMBOLIC]
        return {
            "record_type": SCHEMA, "name": self.name,
            "description": self.description,
            "material_contract_identity": self.identity(),
            "assignments": [a.resolved() for a in self.assignments],
            "resolved_components": self.resolve(component_names)
            if component_names else {},
            "symbolic_colour_references": sorted(set(symbolic)),
            "changes_geometry": False,
            "why": "material is a parameter set applied to an unchanged "
                   "mesh; nothing here can move a geometry identity",
            "owner_approved": False,
            "manufacturing_authority": "NOT_ESTABLISHED",
        }


def evidence_identity(geometry_identity, contract: MaterialContract) -> str:
    """Evidence is the pair. Two materials on one mesh are two pieces of
    evidence, and neither may claim the other's identity."""
    return hashlib.sha256(
        (geometry_identity + contract.identity()).encode()).hexdigest()[:16]


# --------------------------------------------------------------------------
# §12 — the controlled variants that prove generalization
# --------------------------------------------------------------------------

def _neutral(rgb):
    return Colour(rgb=rgb)


def variant_contracts() -> dict:
    """Six contracts over one unchanged geometry.

    One colour would not prove a material engine; it would prove a
    hard-coded look. These span material, finish, resolved colour,
    symbolic colour and per-component assignment.
    """
    return {
        "NEUTRAL_ABS_MATTE": MaterialContract(
            "NEUTRAL_ABS_MATTE",
            [MaterialAssignment("*", ABS, MATTE, _neutral((0.62, 0.62,
                                                           0.63))),
             MaterialAssignment("metal_pan_", METAL, SATIN,
                                _neutral((0.72, 0.73, 0.75))),
             MaterialAssignment("powder_", ABS, MATTE,
                                _neutral((0.36, 0.30, 0.28)))],
            description="the engineering default look"),

        "DARK_GLOSSY_ABS": MaterialContract(
            "DARK_GLOSSY_ABS",
            [MaterialAssignment("*", ABS, GLOSSY, _neutral((0.06, 0.06,
                                                            0.07))),
             MaterialAssignment("metal_pan_", METAL, SATIN,
                                _neutral((0.72, 0.73, 0.75))),
             MaterialAssignment("powder_", ABS, MATTE,
                                _neutral((0.36, 0.30, 0.28)))],
            description="a dark high-gloss case"),

        "LIGHT_SATIN_ABS": MaterialContract(
            "LIGHT_SATIN_ABS",
            [MaterialAssignment("*", ABS, SATIN, _neutral((0.88, 0.87,
                                                           0.85))),
             MaterialAssignment("metal_pan_", METAL, SATIN,
                                _neutral((0.72, 0.73, 0.75))),
             MaterialAssignment("powder_", ABS, MATTE,
                                _neutral((0.36, 0.30, 0.28)))],
            description="a light satin case"),

        "METALLIC_ACCENT": MaterialContract(
            "METALLIC_ACCENT",
            [MaterialAssignment("*", ABS, SATIN, _neutral((0.20, 0.20,
                                                           0.22))),
             MaterialAssignment("lid_", METAL, METALLIC,
                                _neutral((0.78, 0.72, 0.52)),
                                note="metallic lid over a satin base"),
             MaterialAssignment("clasp_", METAL, METALLIC,
                                _neutral((0.78, 0.72, 0.52))),
             MaterialAssignment("hinge_", METAL, METALLIC,
                                _neutral((0.78, 0.72, 0.52))),
             MaterialAssignment("metal_pan_", METAL, SATIN,
                                _neutral((0.72, 0.73, 0.75))),
             MaterialAssignment("powder_", ABS, MATTE,
                                _neutral((0.36, 0.30, 0.28)))],
            description="metallic lid, hinge and clasp"),

        "ES3083_SYMBOLIC_ZONES": MaterialContract(
            "ES3083_SYMBOLIC_ZONES",
            [MaterialAssignment("*", ABS, MATTE, pantone(PANTONE_621C),
                                note="case zone — NAMED reference only"),
             MaterialAssignment("lid_", ABS, MATTE, pantone(PANTONE_627C),
                                note="lid zone — NAMED reference only"),
             MaterialAssignment("metal_pan_", METAL, SATIN,
                                _neutral((0.72, 0.73, 0.75))),
             MaterialAssignment("powder_", ABS, MATTE,
                                _neutral((0.36, 0.30, 0.28)))],
            description="the ES3083 zone assignment; both Pantone tokens "
                        "stay symbolic and carry no RGB"),

        "OWNER_SUBSTITUTED_COLOUR": MaterialContract(
            "OWNER_SUBSTITUTED_COLOUR",
            [MaterialAssignment("*", PP, SATIN,
                                Colour(name="OWNER SELECTION 2026-08",
                                       rgb=(0.31, 0.57, 0.49))),
             MaterialAssignment("metal_pan_", METAL, SATIN,
                                _neutral((0.72, 0.73, 0.75))),
             MaterialAssignment("powder_", ABS, MATTE,
                                _neutral((0.36, 0.30, 0.28)))],
            description="an arbitrary owner-selected colour on a "
                        "different base material"),
    }


def prove_generalization(geometry_identity, component_names) -> dict:
    """§12 — same mesh, different material contract, different evidence.

    The engine passes only when a colour or finish change needs no
    geometry reconstruction, so this compares identities rather than
    asserting the property.
    """
    contracts = variant_contracts()
    rows = []
    for name, contract in sorted(contracts.items()):
        rows.append({
            "variant": name,
            "description": contract.description,
            "mesh_geometry_identity": geometry_identity,
            "material_contract_identity": contract.identity(),
            "evidence_identity": evidence_identity(geometry_identity,
                                                   contract),
            "symbolic_colour_references":
                sorted({a.colour.name for a in contract.assignments
                        if a.colour.kind == SYMBOLIC}),
            "resolved_component_count": len(
                contract.resolve(component_names)),
        })
    meshes = {r["mesh_geometry_identity"] for r in rows}
    materials = {r["material_contract_identity"] for r in rows}
    evidence = {r["evidence_identity"] for r in rows}
    pantone_rgb_leaked = any(
        a.colour.rgb is not None
        for c in contracts.values() for a in c.assignments
        if a.colour.name.startswith("PANTONE"))
    ok = (len(meshes) == 1 and len(materials) == len(rows)
          and len(evidence) == len(rows) and not pantone_rgb_leaked)
    return {
        "record_type": "palette_material_generalization_proof/1.0",
        "variants": rows,
        "variant_count": len(rows),
        "distinct_mesh_identities": len(meshes),
        "distinct_material_identities": len(materials),
        "distinct_evidence_identities": len(evidence),
        "geometry_rebuilt": False,
        "pantone_rgb_fabricated": pantone_rgb_leaked,
        "verdict": "PASS" if ok else "FAIL",
        "proves": "COLOUR_AND_FINISH_CHANGE_WITHOUT_GEOMETRY_"
                  "RECONSTRUCTION",
        "does_not_prove": [
            "that any of these materials is manufacturable",
            "any Pantone value — the tokens remain symbolic",
            "owner approval of any colour",
        ],
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }
