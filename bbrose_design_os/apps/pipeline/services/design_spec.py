"""Rescue v1: an authored, versioned bottle master, never inferred from a picture.

The first supported stock has owner-provided envelope dimensions. Its print
zone and illustrative closure are proposals, explicitly separate from facts.
This schema deliberately cannot assert supplier or creative approval.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from PIL import Image as PILImage
from pydantic import BaseModel, ConfigDict, Field, model_validator

APP_ROOT = Path(__file__).resolve().parents[3]
PRESET_ROOT = APP_ROOT / "docs/design_presets/s2422-sun-repair-v1"
SCHEMA = "design_spec/1.0"
BACKEND = "hybrid_bottle"
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Coordinate = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Hex = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


def digest(value) -> str:
    data = value if isinstance(value, bytes) else json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, serialize_by_alias=True)


class StockSpec(Strict):
    stock_id: Literal["S-2422-type"]
    revision: Literal[1]
    capacity_ml: Literal[30]
    diameter_mm: Literal[29.0]
    height_mm: Literal[108.0]
    height_datum: Literal["overall", "unresolved"]
    authority: Literal["owner_provided"]
    source: Literal["owner rescue brief, 18 October 2026"]
    body_material: Literal["clear_glass"]
    closure_material: Literal["chrome_spray"]
    supplier_verified: Literal[False]


class SurfaceSpec(Strict):
    surface_id: Literal["body.front", "body.back"]
    units: Literal["mm"]
    width_mm: Literal[32.0]
    height_mm: Literal[60.0]
    authority: Literal["design_proposal"]
    method: Literal["unresolved", "screen_print", "label"]
    safe_mm: Literal[2.5]
    bleed_mm: Coordinate
    seam_exclusion_mm: None  # no supplier information exists yet
    uv_transform: Literal["unrolled_cylindrical_arc"]
    angular_center_degrees: Literal[0, 180]
    supplier_verified: Literal[False]

    @model_validator(mode="after")
    def bounded(self):
        if not (20 <= self.width_mm <= 44 and 45 <= self.height_mm <= 65):
            raise ValueError("This first template supports a 20–44 × 45–65 mm proposed front only.")
        if self.safe_mm < 2 or self.safe_mm * 2 >= min(self.width_mm, self.height_mm):
            raise ValueError("The proposed safe margin must leave room for the artwork.")
        if self.bleed_mm != 0:
            raise ValueError("Bleed requires a confirmed label cutline; it is unresolved in this proof.")
        return self


class CopySpec(Strict):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    descriptor: Annotated[str, Field(min_length=1, max_length=60)]
    benefit: Annotated[str, Field(min_length=1, max_length=120)]
    care: Annotated[str, Field(min_length=1, max_length=120)]
    arabic: Annotated[str, Field(min_length=1, max_length=120)]
    volume: Annotated[str, Field(min_length=1, max_length=60)]

    @model_validator(mode="after")
    def readable(self):
        for key, value in self.model_dump().items():
            if not value.strip() or any(ord(c) < 32 and c != "\n" for c in value):
                raise ValueError("Required copy must contain visible text without control characters.")
            if any(line != line.strip() or not line for line in value.split("\n")):
                raise ValueError("Remove blank lines and spaces at the beginning or end of each copy line.")
            if "\n" in value and key not in ("name", "care"):
                raise ValueError(f"The {key} field has one line in this template.")
        return self


class AssetPin(Strict):
    asset_id: str
    sha256: Digest
    role: Literal["illustration", "concept_reference", "approved_logo", "symbol_source"]


class TypeToken(Strict):
    role: Literal["name", "body", "arabic"]
    font_role: str
    sha256: Digest
    size_pt: Positive

    @model_validator(mode="after")
    def fixed_size(self):
        if self.size_pt != {"name": 22.0, "body": 6.5, "arabic": 8.5}[self.role]:
            raise ValueError("This template requires its verified type sizes; a new layout needs a new template.")
        return self


class Palette(Strict):
    dominant: Hex
    secondary: Hex
    accent: Hex


class Illustration(Strict):
    asset_id: Literal["solar-gesture-v1"]
    x_mm: Coordinate
    y_mm: Coordinate
    width_mm: Positive
    height_mm: Positive
    role: Literal["supporting_artwork"]
    visible_from_y_mm: Literal[34.0]


class ElevationProposal(Strict):
    authority: Literal["design_assumption"]
    purpose: Literal["front_back_elevations_only"]
    cap_height_mm: Literal[32.0]
    cap_width_mm: Literal[21.0]
    collar_height_mm: Literal[3.4]
    collar_width_mm: Literal[23.4]
    shoulder_height_mm: Literal[5.0]
    decoration_top_mm: Literal[41.0]


class DesignSpec(Strict):
    schema_version: Literal["design_spec/1.0"]
    revision: Annotated[int, Field(ge=1)]
    parent_hash: Digest | None
    brief: Annotated[str, Field(min_length=1, max_length=8000)]
    brief_hash: Digest
    direction_id: Literal["solar-signature-authored-v1"]
    stock: StockSpec
    surface: SurfaceSpec
    back_surface: SurfaceSpec
    illustration_geometry: ElevationProposal
    copy_surfaces: dict[str, str]
    required_copy: CopySpec = Field(alias="copy")
    palette: Palette
    type_tokens: list[TypeToken]
    assets: list[AssetPin]
    illustration: Illustration
    finish_intent: Literal["none_requested"]
    layer_roles: list[Literal["artwork", "typography", "logo"]]
    proof_annotations: list[Literal["safe", "dimensions"]]
    creative_acceptance: Literal["review_pending"]

    @model_validator(mode="after")
    def coherent(self):
        if self.brief_hash != digest(self.brief.encode()):
            raise ValueError("The brief hash does not match this revision's words.")
        if (self.revision == 1) != (self.parent_hash is None):
            raise ValueError("Every later revision must name its parent master.")
        if sorted(a.asset_id for a in self.assets) != sorted(ASSET_FILES):
            raise ValueError("This template requires its pinned logo, illustration and concept reference.")
        if sorted(t.role for t in self.type_tokens) != ["arabic", "body", "name"]:
            raise ValueError("Name, body and Arabic type tokens are required exactly once.")
        if self.layer_roles != ["artwork", "typography", "logo"] or self.proof_annotations != ["safe", "dimensions"]:
            raise ValueError("Required artwork and proof layer roles changed.")
        a, s = self.illustration, self.surface
        if (a.x_mm, a.y_mm, a.width_mm, a.height_mm) != (0.0, 12.0, 32.0, 48.0):
            raise ValueError("This template uses one unchanged full-width illustration, cropped below the quiet field.")
        if self.surface.surface_id != "body.front" or self.back_surface.surface_id != "body.back":
            raise ValueError("The front and back surfaces must retain their identity.")
        if (self.surface.angular_center_degrees, self.back_surface.angular_center_degrees) != (0, 180):
            raise ValueError("The proposed front and back decorations must face opposite directions.")
        if self.surface.method != self.back_surface.method:
            raise ValueError("This first two-surface template uses one proposed decoration method.")
        expected = {key: "body.front" if key in ("name", "descriptor", "arabic") else "body.back"
                    for key in DEFAULT_COPY}
        if self.copy_surfaces != expected:
            raise ValueError("Every required copy field must have its declared front or back placement.")
        return self


ASSET_FILES = {
    "solar-gesture-v1": (PRESET_ROOT / "solar-gesture.png", "illustration"),
    "sun-repair-concept-147": (PRESET_ROOT / "concept-reference.png", "concept_reference"),
    "bbrose-approved-logo": (APP_ROOT / "docs/brand/mark/bbrose-logo.svg", "approved_logo"),
    "estimated-sign-source": (APP_ROOT / "static/fonts/brand2026/Montserrat/Montserrat-Regular.ttf", "symbol_source"),
}
FONT_ROLES = {"name": "line-face:BarlowCondensed-Bold@700", "body": "line-face:Poppins-Regular@400",
              "arabic": "arabic-body"}
DEFAULT_COPY = dict(name="SUN\nREPAIR", descriptor="SERUM", benefit="Revive + Smooth",
                    care="Daily Antioxidant Care", arabic="سيروم صن ريبير", volume="30 ml ℮ 1.0 fl oz")


def resolve_fonts(tokens):
    from apps.ire.font_roles import parse_line_face, resolve_line_face, resolve_role
    result = {}
    for token in tokens:
        if token.font_role != FONT_ROLES[token.role]:
            raise ValueError("This template's licensed type pairing has changed; select a supported face.")
        parsed = parse_line_face(token.font_role)
        row = resolve_line_face(*parsed) if parsed else resolve_role(token.font_role)
        if row.get("refused") or row.get("sha256") != token.sha256:
            raise ValueError(f"The licensed {token.role} font is missing or its bytes changed.")
        result[token.role] = row
    return result


def resolve_assets(spec: DesignSpec):
    """Paths are chosen by the server, never supplied by JSON or a browser."""
    from apps.ire.brand_mark import approved_master
    resolved = {}
    manifest = json.loads((PRESET_ROOT / "asset-manifest.json").read_text())["assets"]
    for pin in spec.assets:
        path, role = ASSET_FILES[pin.asset_id]
        if pin.role != role or pin.sha256 != manifest[pin.asset_id]["sha256"] or not path.is_file() or digest(path.read_bytes()) != pin.sha256:
            raise ValueError(f"The required {role.replace('_', ' ')} is missing or changed.")
        resolved[pin.asset_id] = path
    approval = approved_master()
    if not approval.get("master") or approval["master"].asset_id != "brand-mark:" + next(
            a.sha256 for a in spec.assets if a.role == "approved_logo"):
        raise ValueError("The logo master no longer has its recorded approval.")
    a = spec.illustration
    with PILImage.open(resolved[a.asset_id]) as bitmap:
        ppi = [bitmap.width * 25.4 / a.width_mm, bitmap.height * 25.4 / a.height_mm]
        if min(ppi) < 300:
            raise ValueError("Illustration is below 300 effective PPI at this placement.")
        if abs((bitmap.width / bitmap.height) / (a.width_mm / a.height_mm) - 1) > 0.001:
            raise ValueError("Illustration placement changes its aspect ratio.")
    return resolved, ppi


def validate_spec(data, *, expected_hash=None):
    spec = DesignSpec.model_validate(data)
    if expected_hash is not None and digest(spec.model_dump()) != expected_hash:
        raise ValueError("The saved master changed after this revision was queued.")
    resolve_assets(spec)
    resolve_fonts(spec.type_tokens)
    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))
    a, b = sorted([luminance(spec.palette.dominant), luminance(spec.palette.secondary)])
    if (b + .05) / (a + .05) < 4.5:
        raise ValueError("The lettering and field colours have too little contrast for this proof.")
    return spec


def make_spec(*, copy=None, height_datum="unresolved", method="unresolved", revision=1,
              parent_hash=None, palette=None):
    from apps.ire.font_roles import parse_line_face, resolve_line_face, resolve_role
    copy = DEFAULT_COPY if copy is None else copy
    brief = "30 ml clear glass S-2422-type, Ø29 × 108 mm, chrome spray cap.\n" + "\n".join(copy.values())
    tokens = []
    for role, font in FONT_ROLES.items():
        parsed = parse_line_face(font)
        row = resolve_line_face(*parsed) if parsed else resolve_role(font)
        if row.get("refused"):
            raise ValueError(f"The licensed {role} font is unavailable.")
        tokens.append(dict(role=role, font_role=font, sha256=row["sha256"],
                           size_pt={"name": 22.0, "body": 6.5, "arabic": 8.5}[role]))
    manifest = json.loads((PRESET_ROOT / "asset-manifest.json").read_text())["assets"]
    return validate_spec(dict(
        schema_version=SCHEMA, revision=revision, parent_hash=parent_hash, brief=brief,
        brief_hash=digest(brief.encode()), direction_id="solar-signature-authored-v1",
        stock=dict(stock_id="S-2422-type", revision=1, capacity_ml=30, diameter_mm=29.0, height_mm=108.0,
                   height_datum=height_datum, authority="owner_provided", source="owner rescue brief, 18 October 2026",
                   body_material="clear_glass", closure_material="chrome_spray", supplier_verified=False),
        surface=dict(surface_id="body.front", units="mm", width_mm=32.0, height_mm=60.0,
                     authority="design_proposal", method=method, safe_mm=2.5, bleed_mm=0.0,
                     seam_exclusion_mm=None, uv_transform="unrolled_cylindrical_arc", angular_center_degrees=0, supplier_verified=False),
        back_surface=dict(surface_id="body.back", units="mm", width_mm=32.0, height_mm=60.0,
                     authority="design_proposal", method=method, safe_mm=2.5, bleed_mm=0.0,
                     seam_exclusion_mm=None, uv_transform="unrolled_cylindrical_arc", angular_center_degrees=180, supplier_verified=False),
        illustration_geometry=dict(authority="design_assumption", purpose="front_back_elevations_only", cap_height_mm=32.0,
                     cap_width_mm=21.0, collar_height_mm=3.4, collar_width_mm=23.4, shoulder_height_mm=5.0,
                     decoration_top_mm=41.0),
        copy_surfaces={key: "body.front" if key in ("name", "descriptor", "arabic") else "body.back" for key in DEFAULT_COPY},
        copy=copy, palette=palette or dict(dominant="#F6F1E7", secondary="#172A35", accent="#B45C0A"),
        type_tokens=tokens, assets=[dict(asset_id=k, sha256=manifest[k]["sha256"], role=r)
                                   for k, (p, r) in ASSET_FILES.items()],
        illustration=dict(asset_id="solar-gesture-v1", x_mm=0.0, y_mm=12.0, width_mm=32.0, height_mm=48.0,
                          role="supporting_artwork", visible_from_y_mm=34.0), finish_intent="none_requested",
        layer_roles=["artwork", "typography", "logo"], proof_annotations=["safe", "dimensions"], creative_acceptance="review_pending"))


def unresolved(spec):
    items = ["Supplier stock drawing and tolerances", "Cap, nozzle and shoulder dimensions",
             "Printable body region and seam exclusions", "Decoration trials, ink opacity and adhesion",
             "Supplier colour profile and physical proof", "Independent creative and fidelity review",
             "Final multilingual copy review"]
    if spec.stock.height_datum == "unresolved":
        items.insert(0, "Whether 108 mm includes the spray cap")
    if spec.surface.method == "unresolved":
        items.insert(0, "Decoration method")
    if spec.surface.method == "label":
        items.insert(0, "Label cutline, bleed, stock and adhesive")
    return items
