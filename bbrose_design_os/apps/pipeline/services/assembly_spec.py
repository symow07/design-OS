"""Immutable, provenance-bearing countertop assembly inputs. No artwork authoring."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .design_spec import APP_ROOT, digest, validate_spec

BACKEND = "hybrid_assembly"
PIN_HASH = "1b0d5a9c760fa03c2e2662f58f38f3f6b014874a09266533f25cfdefc17f6467"
PIN_ROOT = APP_ROOT.parent / "docs/audit/day-2/master"
EVENT_PATH = APP_ROOT.parent / "docs/audit/day-3/state-events/serum-r1-superseded.json"
PRESET = APP_ROOT / "docs/design_presets/stepped-display-v1"
SURFACES = ("header.front", "header.back", "riser.1.front", "riser.2.front", "riser.3.front",
            "side.left", "side.right", "base.front", "lip.front")
T = TypeVar("T")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Fact(Strict, Generic[T]):
    value: T | None
    authority: Literal["owner_provided", "proposed", "unresolved"]
    source: str = Field(min_length=3)

    @model_validator(mode="after")
    def truthful(self):
        if (self.authority == "unresolved") != (self.value is None):
            raise ValueError("Unresolved facts must be null; a proposed default is a separate fact.")
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise ValueError("A measurement must be finite.")
        return self


class ProductPin(Strict):
    output_id: Fact[str]
    database_output_id: Fact[int]
    spec_hash: Fact[str]
    artifact_hashes: Fact[dict[str, str]]
    use_scope: Fact[str]
    state_event_hash: Fact[str]


class Envelope(Strict):
    profile: Fact[str]
    width_mm: Fact[float]
    depth_mm: Fact[float]
    height_mm: Fact[float]
    capacity_ml: Fact[float]
    height_datum: Fact[str]
    base_contact_profile: Fact[str]
    nozzle_projection_mm: Fact[float]
    filled_mass_g: Fact[float]
    centre_of_gravity_mm: Fact[list[float]]
    retention_clearance_mm: Fact[float]
    cap_height_mm: Fact[float]
    cap_width_mm: Fact[float]
    collar_height_mm: Fact[float]
    collar_width_mm: Fact[float]
    shoulder_height_mm: Fact[float]
    decoration_bottom_mm: Fact[float]
    decoration_height_mm: Fact[float]
    decoration_width_mm: Fact[float]


class Dimensions(Strict):
    width_mm: Fact[float]
    depth_mm: Fact[float]
    height_mm: Fact[float]


class Holes(Strict):
    profile: Fact[str]
    requested_size_mm: Fact[float]
    derived_size_mm: Fact[float]
    nominal_diametral_clearance_mm: Fact[float]
    minimum_web_mm: Fact[float]
    edge_margin_mm: Fact[float]
    chamfer: Fact[str]
    retention: Fact[str]


class Rules(Strict):
    riser_rule: Fact[str]
    fixed_riser_mm: Fact[float]
    base_thickness_mm: Fact[float]
    deck_thickness_mm: Fact[float]
    collar_offset_mm: Fact[float]
    back_web_mm: Fact[float]
    header_height_mm: Fact[float]
    header_thickness_mm: Fact[float]
    header_angle_deg: Fact[float]
    header_attachment: Fact[str]
    lip_height_mm: Fact[float]
    lip_thickness_mm: Fact[float]
    material: Fact[str]
    thickness_mm: Fact[float]
    provisional_material: Fact[str]
    provisional_thickness_mm: Fact[float]
    support_webs: Fact[str]
    joints: Fact[str]
    assembly_method: Fact[str]
    eye_front_mm: Fact[float]
    eye_above_base_mm: Fact[float]
    sightline_clearance_mm: Fact[float]


class AssemblySpec(Strict):
    # Protocol identity is metadata. All domain values below carry provenance.
    schema_version: Literal["assembly_spec/1.0"]
    revision: int = Field(ge=1)
    parent_hash: str | None
    case_id: Fact[str]
    source_brief: Fact[str]
    product: ProductPin
    product_envelope: Envelope
    count: Fact[int]
    rows: Fact[int]
    cols: Fact[int]
    row_order: Fact[str]
    holes: Holes
    rules: Rules
    envelope_requested: Dimensions
    required_languages: Fact[list[str]]
    required_copy_by_surface: Fact[dict[str, list[str]]]
    artwork_binding: Fact[str]
    decks: list[dict] = Field(default_factory=list)
    base: dict[str, Fact[Any]] = Field(default_factory=dict)
    lip: dict[str, Fact[Any]] = Field(default_factory=dict)
    header: dict[str, Fact[Any]] = Field(default_factory=dict)
    supports: dict[str, Fact[Any]] = Field(default_factory=dict)
    print_surfaces: list[dict] = Field(default_factory=list)
    envelope_realised: Dimensions | None = None
    provenance: list[dict] = Field(default_factory=list)

    @model_validator(mode="after")
    def coherent(self):
        if (self.revision == 1) != (self.parent_hash is None):
            raise ValueError("Later assemblies require the exact parent hash.")
        if self.parent_hash is not None and (len(self.parent_hash) != 64 or any(c not in "0123456789abcdef" for c in self.parent_hash)):
            raise ValueError("Invalid parent hash.")
        if (self.count.value, self.rows.value, self.cols.value) != (12, 3, 4):
            raise ValueError("This countertop kit requires exactly twelve bottles in three rows of four.")
        if self.row_order.value != "front_to_back" or self.artwork_binding.value != "pending_day4_fidelity_master":
            raise ValueError("Row order or the Day 4 artwork hold changed.")
        if self.holes.profile.value not in ("circle", "square") or self.product_envelope.profile.value != self.holes.profile.value:
            raise ValueError("The hole profile must match the declared product envelope.")
        for item in (self.envelope_requested.width_mm, self.envelope_requested.depth_mm, self.envelope_requested.height_mm,
                     self.product_envelope.width_mm, self.product_envelope.depth_mm, self.product_envelope.height_mm,
                     self.holes.requested_size_mm, self.holes.minimum_web_mm):
            if item.value is None or not 0 < item.value <= 2000:
                raise ValueError("Required dimensions must be positive, finite and within this countertop kit's range.")
        if self.rules.riser_rule.value not in ("minimum_whole_mm_for_full_visibility", "fixed"):
            raise ValueError("Unknown riser rule.")
        if self.rules.riser_rule.value == "fixed" and (self.rules.fixed_riser_mm.value is None or self.rules.fixed_riser_mm.value <= 0):
            raise ValueError("A fixed riser must have a positive height.")
        fixed_rules = dict(base_thickness_mm=6., deck_thickness_mm=6., collar_offset_mm=0., back_web_mm=10.,
                           header_height_mm=100., header_thickness_mm=6., header_angle_deg=90.,
                           lip_height_mm=6., lip_thickness_mm=6., provisional_thickness_mm=6.,
                           eye_front_mm=500., eye_above_base_mm=350., sightline_clearance_mm=.25)
        if any(getattr(self.rules,k).value != v for k,v in fixed_rules.items()):
            raise ValueError("This version supports only its declared upright 6 mm provisional kit and fixed viewpoint; changed construction needs a new template.")
        if self.rules.thickness_mm.value is not None:
            raise ValueError("No supplier thickness is confirmed in this template.")
        expected = (16.,16.,98.,6.,"square") if self.case_id.value == "146" else (29.,29.,108.,30.,"circle")
        if tuple(getattr(self.product_envelope,k).value for k in ("width_mm","depth_mm","height_mm","capacity_ml","profile")) != expected:
            raise ValueError("The declared product envelope differs from the pinned or original brief dimensions.")
        for path, f in facts(self.model_dump()):
            if isinstance(f["value"], (int, float)) and (not math.isfinite(f["value"]) or f["value"] < 0):
                raise ValueError(f"Invalid negative or non-finite value: {path}")
        return self


def facts(value, prefix=""):
    if isinstance(value, dict):
        if set(value) == {"value", "authority", "source"}:
            yield prefix, value
        else:
            for k, v in value.items():
                yield from facts(v, f"{prefix}.{k}".strip("."))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from facts(v, f"{prefix}[{i}]")


def fact(value, authority="proposed", source="Day 3 declared template proposal"):
    return {"value": value, "authority": authority, "source": source}


def unknown(source):
    return fact(None, "unresolved", source)


def load_pin():
    data = json.loads((PIN_ROOT / "design-spec.json").read_text())
    validate_spec(data, expected_hash=PIN_HASH)
    record = json.loads((PIN_ROOT / "build-record.json").read_text())
    if record["spec_hash"] != PIN_HASH or record["design_spec"] != data:
        raise ValueError("The pinned serum record changed.")
    for name, expected in record["artifact_hashes"].items():
        path = (PIN_ROOT / name).resolve()
        if path.parent != PIN_ROOT.resolve() or not path.is_file() or digest(path.read_bytes()) != expected:
            raise ValueError(f"The pinned serum artifact changed: {name}")
    event = json.loads(EVENT_PATH.read_text())
    if event["subject"]["spec_hash"] != PIN_HASH or event["state"] != "superseded_pending_fidelity_master":
        raise ValueError("The serum supersession record does not match the pinned revision.")
    return data, record, digest(EVENT_PATH.read_bytes())


def validate_assembly(data, *, expected_hash=None, _allow_incomplete=False):
    spec = AssemblySpec.model_validate(data)
    if expected_hash is not None and digest(spec.model_dump()) != expected_hash:
        raise ValueError("Assembly bytes changed after this revision was saved.")
    _, record, event_hash = load_pin()
    if spec.case_id.value != "146" and (spec.product.spec_hash.value != PIN_HASH or spec.product.artifact_hashes.value != record["artifact_hashes"]
            or spec.product.state_event_hash.value != event_hash or spec.product.use_scope.value != "geometry_proposal_only"):
        raise ValueError("The assembly must retain its exact serum pin and geometry-only scope.")
    original = {"144": (180.,150.,300.), "146": (120.,120.,260.)}
    dimensions = tuple(getattr(spec.envelope_requested,k).value for k in ("width_mm","depth_mm","height_mm"))
    if spec.case_id.value in original and dimensions != original[spec.case_id.value]:
        raise ValueError("Original brief envelope changed; use a separate family proposal.")
    inputs = _inputs(spec.case_id.value, revision=spec.revision, parent_hash=spec.parent_hash,
                     dimensions=dimensions if spec.case_id.value=="family-proposal" else None,
                     riser=spec.rules.fixed_riser_mm.value if spec.rules.riser_rule.value=="fixed" else None,
                     hole=spec.holes.derived_size_mm.value if spec.holes.derived_size_mm.value != spec.holes.requested_size_mm.value else None)
    if any(spec.model_dump()[key] != value for key,value in inputs.items()):
        raise ValueError("Assembly input or provenance differs from its pinned geometry and declared template.")
    if not spec.decks and not _allow_incomplete:
        raise ValueError("The assembly must include its derived decks and surfaces.")
    if spec.decks:
        from apps.ire.stepped_display import solve
        wanted = derived_fields(spec, solve(spec))
        actual = spec.model_dump()
        if any(actual[k] != v for k,v in wanted.items()):
            raise ValueError("Derived geometry differs from its authoritative assembly inputs.")
    return spec


def derived_fields(spec, solution):
    w,d,h=solution['envelope_requested'];r=spec.rules
    f=lambda v,source:fact(v,source=source)
    decks=[dict(row=f(row['row'],'Front-to-back row index'),**{k:v for k,v in row.items() if k!='row'}) for row in solution['decks']]
    realised=solution['envelope_realised']
    provenance=[v for v in solution['provenance'] if not v['field'].startswith(('decks','base.','lip.','header.','supports.','print_surfaces','envelope_realised','provenance'))]
    return dict(decks=decks,
                base=dict(width_mm=spec.envelope_requested.width_mm.model_dump(),depth_mm=spec.envelope_requested.depth_mm.model_dump(),thickness_mm=r.base_thickness_mm.model_dump()),
                lip=dict(width_mm=spec.envelope_requested.width_mm.model_dump(),height_mm=r.lip_height_mm.model_dump(),thickness_mm=r.lip_thickness_mm.model_dump()),
                header=dict(width_mm=spec.envelope_requested.width_mm.model_dump(),height_mm=r.header_height_mm.model_dump(),angle_deg=r.header_angle_deg.model_dump(),attachment=r.header_attachment.model_dump()),
                supports=dict(webs=r.support_webs.model_dump(),joints=r.joints.model_dump(),assembly_method=r.assembly_method.model_dump()),
                print_surfaces=solution['print_surfaces'],
                envelope_realised={k:f(v,'Measured from all model solids; refused diagnostics may exceed the requested envelope') for k,v in zip(('width_mm','depth_mm','height_mm'),realised)} if realised else None,
                provenance=provenance)


def _inputs(case_id="family-proposal", *, revision=1, parent_hash=None, dimensions=None, riser=None, hole=None):
    data, record, event_hash = load_pin()
    briefs = json.loads((PRESET / "original-briefs.json").read_text())
    if case_id not in ("family-proposal", "144", "146"):
        raise ValueError("Only the serum family and the two declared acceptance briefs are available.")
    square = case_id == "146"
    source = f"Stored task {case_id} brief, preserved verbatim" if case_id != "family-proposal" else "Owner Day 3 serum family instruction"
    own = lambda v: fact(v, "owner_provided", source)
    width, height, hole_size = (16., 98., 18.) if square else (29., 108., 31.)
    env = dict(profile=own("square" if square else "circle"), width_mm=own(width), depth_mm=own(width), height_mm=own(height),
               capacity_ml=own(6. if square else 30.), height_datum=unknown("Stored brief gives approximate height without datum"),
               base_contact_profile=unknown("No measured base/heel profile"), nozzle_projection_mm=unknown("No nozzle projection measurement"),
               filled_mass_g=unknown("No filled product mass"), centre_of_gravity_mm=unknown("No measured centre of gravity"),
               retention_clearance_mm=unknown("No supplier tolerance or retention trial"))
    for name in ("cap_height_mm", "cap_width_mm", "collar_height_mm", "collar_width_mm", "shoulder_height_mm"):
        env[name] = unknown("Kiss Me vial has no measured closure geometry") if square else fact(float(data["illustration_geometry"][name]), source="Pinned Day 2 ElevationProposal; not stock geometry")
    for name, value in (("decoration_bottom_mm", 7.), ("decoration_height_mm", 60.), ("decoration_width_mm", 32.)):
        env[name] = unknown("Kiss Me has no declared decoration map; S-2422 mapping cannot be transferred") if square else fact(value, source="Pinned ElevationProposal: 108 - 41 - 60 = 7 mm; superseded artwork used only as sightline test region")
    requested = (120., 120., 260.) if square else ((180., 150., 300.) if case_id == "144" else (180., 150., 420.))
    if case_id != "family-proposal" and dimensions is not None and tuple(dimensions) != requested:
        raise ValueError("Original brief envelope changed; use a separate family proposal.")
    if case_id != "family-proposal": dimensions = None
    if hole is not None and float(hole) == hole_size: hole = None
    dims = dimensions or requested
    dim_source = source if case_id != "family-proposal" and dimensions is None else "Explicit new envelope proposal; does not replace either original brief"
    dim_auth = "owner_provided" if case_id != "family-proposal" and dimensions is None else "proposed"
    h = hole_size if hole is None else float(hole)
    copies = ({"header.front": ["BBROSE", "Kiss Me", "Lip Gloss / ملمّع الشفاه", "Embrace the kissable you"],
               "lip.front": ["Kiss Me · 6 ml"], "side.left": ["BBROSE logo; leopard pattern"], "side.right": ["BBROSE logo; leopard pattern"]} if square else
              {"header.front": ["BBROSE", "Ginkgo Mist", "Hydrating Face Mist / رذاذ الوجه", "Calm. Fresh. Hydrated."],
               "lip.front": ["Ginkgo Mist · 30 ml ℮ 1.0 fl oz"], "side.left": ["BBROSE logo; swirl pattern"], "side.right": ["BBROSE logo; swirl pattern"]})
    if case_id == "family-proposal":
        copies = {"header.front": [], "lip.front": [], "side.left": [], "side.right": []}
    rules = {k: fact(v) for k, v in dict(base_thickness_mm=6., deck_thickness_mm=6., collar_offset_mm=0., back_web_mm=10.,
              header_height_mm=100., header_thickness_mm=6., header_angle_deg=90., lip_height_mm=6., lip_thickness_mm=6.,
              provisional_material="cardboard board model; construction grade unconfirmed", provisional_thickness_mm=6.,
              support_webs="two longitudinal webs plus rear panel; contacts shown, joints unresolved",
              eye_front_mm=500., eye_above_base_mm=350., sightline_clearance_mm=.25).items()}
    rules.update(riser_rule=fact("fixed" if riser is not None else "minimum_whole_mm_for_full_visibility"),
                 fixed_riser_mm=fact(float(riser), source="Explicit proposed fixed riser") if riser is not None else unknown("Auto rule chooses a whole-mm rise"),
                 header_attachment=unknown("No attachment method supplied"), material=own("printed cardboard") if case_id != "family-proposal" else unknown("Family material has not been selected"),
                 thickness_mm=unknown("Brief supplies no board thickness"), joints=unknown("No fold, tab, glue or fastener details supplied"),
                 assembly_method=unknown("Preliminary solid seats and separate collars; fabricator assembly method pending"))
    pin = dict(output_id=fact("published:rescue-day-2:serum-r1", source="Day 2 canonical published artifact bundle; no database output ID exists"),
               database_output_id=unknown("Day 2 sample was published without a database PackagingOutput row"),
               spec_hash=fact(PIN_HASH, "owner_provided", "Day 3 owner instruction: exact serum revision pin"), artifact_hashes=fact(record["artifact_hashes"], source="Immutable Day 2 build-record.json"),
               use_scope=fact("geometry_proposal_only", source="Owner Day 3 exclusion: no artwork binding"),
               state_event_hash=fact(event_hash, source="D-D3-1 immutable supersession event"))
    if square:
        pin = dict(output_id=own("declared:task-146:Kiss-Me-vial"),
                   database_output_id=unknown("No measured vial master output exists"),
                   spec_hash=unknown("Declared vial envelope only; this product is not the serum pin"),
                   artifact_hashes=unknown("No vial master artifacts supplied"),
                   use_scope=fact("declared_envelope_only", source="Original task 146 dimensions; no serum geometry transferred"),
                   state_event_hash=unknown("Serum supersession event does not apply to this separate vial"))
    return dict(schema_version="assembly_spec/1.0", revision=revision, parent_hash=parent_hash,
        case_id=own(case_id), source_brief=own(briefs[case_id] if case_id in briefs else "Twelve-bottle serum family, three stepped rows of four. Separate taller envelope proposal for full visibility; original task 144 remains 180 × 150 × 300 mm."),
        product=pin, product_envelope=env, count=own(12), rows=own(3), cols=own(4), row_order=own("front_to_back"),
        holes=dict(profile=own("square" if square else "circle"), requested_size_mm=own(hole_size), derived_size_mm=fact(h, source="Requested hole retained" if hole is None else "Explicit new hole proposal"),
                   nominal_diametral_clearance_mm=fact(h-width, source="Hole size minus product width; not validated retention clearance"),
                   minimum_web_mm=fact(4.), edge_margin_mm=fact(4.), chamfer=unknown("No edge/chamfer treatment specified"), retention=unknown("Separate collar locates, solid seat supports; retention trial pending")),
        rules=rules, envelope_requested={k: fact(float(v), dim_auth, dim_source) for k, v in zip(("width_mm", "depth_mm", "height_mm"), dims)},
        required_languages=own(["EN", "AR"]), required_copy_by_surface=own(copies), artwork_binding=own("pending_day4_fidelity_master"))


def make_assembly(case_id="family-proposal", *, revision=1, parent_hash=None, dimensions=None, riser=None, hole=None):
    from apps.ire.stepped_display import solve
    raw = _inputs(case_id,revision=revision,parent_hash=parent_hash,dimensions=dimensions,riser=riser,hole=hole)
    spec = validate_assembly(raw, _allow_incomplete=True)
    return validate_assembly(dict(spec.model_dump(), **derived_fields(spec,solve(spec))))
