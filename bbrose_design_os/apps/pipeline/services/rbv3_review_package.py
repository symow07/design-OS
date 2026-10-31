"""RBV-3 — standard visual review package (``rbv3_review_package/1.0``).

Generalizes the ad-hoc P1 review boards into the STANDARD package the RBV
architecture §5 names: one package per subject, assembled ONLY from a
hash-verified RBV-2B geometry-validation render manifest, quoting the
camera/lighting standards at their live recorded status (a citation never
upgrades a PROPOSED contract to ACTIVE), and stating the client-
presentation mode's absence explicitly — validation renders are never
re-badged as presentation (§1 two-mode principle).

Fail-closed: missing manifest, schema mismatch, missing view or decoded-
pixel hash mismatch refuse with exact findings. A view file may be
REBOUND to a renamed file only when its decoded-pixel hash proves
identity with the recorded render (the V4 evidence-dir precedent); the
rebinding is recorded in the package manifest, never silent.

Storage policy: view PNGs are REFERENCED (repo-relative source dir + name
+ recorded decoded-pixel hash), never copied — the render evidence is
already committed and immutable, and copying multiplies tens of MB per
subject. The package's own artifact is the contact sheet, which composites
every view; the dashboard serves full-resolution views from the recorded
source. Reference photographs ARE copied: they come from outside the
render evidence tree.

READ-ONLY over render evidence; no provider calls; no Django ORM. Owner
decisions never land here — the manifest names the clearance-sheet
channel BY RULE and carries no decision fields.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil

from PIL import Image, ImageDraw, ImageFont

from apps.pipeline.services.geometry_validation_render import (
    MANIFEST_SCHEMA as RENDER_MANIFEST_SCHEMA,
    pixel_hash,
)

SCHEMA = "rbv3_review_package/1.0"

MODE_GEOMETRY_VALIDATION = "GEOMETRY_VALIDATION"
MODE_CLIENT_PRESENTATION = "CLIENT_PRESENTATION"

RBV3_RENDER_MANIFEST_MISSING = "RBV3_RENDER_MANIFEST_MISSING"
RBV3_RENDER_SCHEMA_MISMATCH = "RBV3_RENDER_SCHEMA_MISMATCH"
RBV3_VIEW_MISSING = "RBV3_VIEW_MISSING"
RBV3_VIEW_HASH_MISMATCH = "RBV3_VIEW_HASH_MISMATCH"
RBV3_REFERENCE_CLASS_INVALID = "RBV3_REFERENCE_CLASS_INVALID"
RBV3_REFERENCE_FILE_MISSING = "RBV3_REFERENCE_FILE_MISSING"
RBV3_SHEET_FONT_UNAVAILABLE = "RBV3_SHEET_FONT_UNAVAILABLE"
RBV3_SHEET_TEXT_ILLEGIBLE = "RBV3_SHEET_TEXT_ILLEGIBLE"
RBV3_RENDER_MANIFEST_INCOMPLETE = "RBV3_RENDER_MANIFEST_INCOMPLETE"
RBV3_VIEW_HASH_ABSENT = "RBV3_VIEW_HASH_ABSENT"

#: §AL3(a)/§R4 — THE HONESTY FIELDS, required rather than defaulted.
#:
#: Every one of these was previously read through a defaulted lookup
#: supplying an empty substitute, and every one of those reads was
#: recorded as a defect and LEFT FAILING under §R4c. They share a shape:
#: the substitute is not a neutral placeholder but a POSITIVE CLAIM.
#: An absent `warnings` renders as "warnings: none"; an
#: absent `statement` removes the caveat that says these are validation
#: renders and not a real bottle; an absent `uncertainty` persists as "no
#: uncertainty declared" on a package whose purpose is honest qualification.
#: A field that means something when present cannot mean nothing when
#: absent, so absence is refused at the boundary and every downstream read
#: is a direct index. The list is the enforcement; the reads are consequences
#: of it.
REQUIRED_RENDER_MANIFEST_FIELDS = (
    "statement", "views", "pixel_hashes", "dimensions",
    "reference_availability",
    #: §AL3(a)/§AP. The sheet's last line reads "source: RBV-2B manifest
    #: sha256 <hash> · <blender_version> · <render_engine>". Both were
    #: defaulted to the empty string, so a manifest naming neither still
    #: drew a line beginning "source:" with nothing after it — a
    #: provenance claim containing no provenance, indistinguishable from
    #: a render genuinely made by an engine nobody named. Every committed
    #: RBV-2B manifest carries both, so requiring them refuses only
    #: manifests RBV-2B did not write.
    "blender_version", "render_engine",
)
#: PRESENT, a mapping, and NON-EMPTY — and the asymmetry with the LISTS
#: below is deliberate rather than an oversight. `warnings: []` is a
#: measurement: the render raised nothing. `measurements: {}` is not —
#: "we measured and found no measurements" is not a state RBV-2B can
#: honestly be in, and the contact sheet draws §11 under the heading
#: "MEASUREMENTS (render manifest, verbatim)", which asserts verbatim
#: fidelity to something that has to exist to be verbatim about.
REQUIRED_RENDER_MANIFEST_MAPS = ("measurements",)
#: PRESENT and a list, but legitimately EMPTY. This split is the whole
#: point of the defect and must not be collapsed back: a render that
#: genuinely raised no warnings records `[]`, and that is a measurement.
#: A render whose manifest never mentioned warnings records nothing, and
#: that is an absence. Requiring these to be TRUTHY would refuse the
#: honest clean render (the committed 2026-08-04 manifest carries
#: `warnings: []`) and would re-collapse the two states this refuses to
#: confuse — which is the defect one level up.
REQUIRED_RENDER_MANIFEST_LISTS = ("warnings", "uncertainty")
#: the contract dimensions restated legibly on the sheet. `side_depth_mm`
#: is named explicitly because its absence used to print the FRONT WIDTH
#: under a `D` label — a wrong number wearing a measured one's clothes,
#: invisible in the committed evidence only because that subject happens
#: to have W == D.
REQUIRED_DIMENSION_FIELDS = ("height_mm", "front_width_mm", "side_depth_mm")

#: §S2. The reviewing provider downscales any image whose long edge exceeds
#: this, so a sheet's text is not legible at the size it was DRAWN — it is
#: legible at the size that SURVIVES the downscale. Legibility is therefore
#: arithmetic and is measured here, never asserted.
PROVIDER_LONG_EDGE_LIMIT = 2576
#: floor for composer-drawn text, in effective pixels after downscale
SHEET_TEXT_MIN_EFFECTIVE_PX = 12.0

#: why mode B is absent from every package this module can emit today —
#: rbv2c is unbuilt AND gated behind owner inspection of pilot geometry
#: (P1_OWNER_VISUAL_APPROVAL: NOT_GRANTED). Both must clear.
PRESENTATION_ABSENT_REASONS = (
    "RBV2C_PRESENTATION_RENDERER_NOT_BUILT",
    "OWNER_GATE_PILOT_GEOMETRY_INSPECTION_PENDING",
)
TWO_MODE_RULE = ("validation renders are never re-badged as presentation "
                 "(§1 two-mode principle); geometry verdicts come only "
                 "from mode A")

#: the only admissible reference evidence classes; every reference panel
#: carries the calibration disclaimer verbatim
REFERENCE_EVIDENCE_CLASSES = ("OWNER_PHOTOGRAPH_UNCALIBRATED",)
REFERENCE_DISCLAIMER = ("perspective + uncalibrated — qualitative "
                        "juxtaposition only; NO calibrated overlay "
                        "accuracy is claimed")

DECISION_CHANNEL = ("owner reviews are QUEUED in OWNER_REVIEW_QUEUE.md and "
                    "decided ONLY through OWNER_BLOCKER_CLEARANCE.md — no "
                    "decision endpoint exists in this package by rule")

CANONICAL_VIEW_ORDER = ("front", "side", "top", "closure_detail",
                        "bounds_dimensions", "three_quarter_diagnostic",
                        "wireframe", "normals")

_REPO = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
_RBV_DOCS = os.path.join(_REPO, "docs", "visual_quality", "rbv")
_FONT = "/System/Library/Fonts/Helvetica.ttc"
SHEET_NAME = "review_contact_sheet.png"
MANIFEST_NAME = "review_package_manifest.json"

VIEW_STORAGE_POLICY = (
    "views are REFERENCED from the committed render evidence (source_dir + "
    "source_file + recorded decoded-pixel hash), never copied; the contact "
    "sheet is the package's own artifact")


def _repo_relative(path: str) -> str:
    return os.path.relpath(os.path.realpath(path), _REPO)


class Rbv3Refusal(ValueError):
    """Fail-closed package refusal; ``findings`` lists exact codes."""

    def __init__(self, findings):
        self.findings = list(findings)
        super().__init__("; ".join(self.findings))


def _font(size):
    """No silent substitution: a different font is a different contact
    sheet and a different recorded pixel hash, so an absent font REFUSES
    rather than degrading to the PIL default."""
    try:
        return ImageFont.truetype(_FONT, size)
    except OSError as exc:                        # pragma: no cover
        raise Rbv3Refusal([f"{RBV3_SHEET_FONT_UNAVAILABLE}:{_FONT}"]) \
            from exc


def _file_sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _glyph_px(text: str, size: int) -> int:
    """Rendered height of ``text`` at ``size``, measured — not derived from
    the nominal point size, which overstates it."""
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    box = probe.textbbox((0, 0), text, font=_font(size))
    return box[3] - box[1]


def provider_downscale(long_edge: int) -> float:
    """The factor the reviewing provider applies to an image of this long
    edge. 1.0 when it is already within the limit."""
    return min(PROVIDER_LONG_EDGE_LIMIT / float(long_edge), 1.0)


def sheet_legibility(sheet_long_edge: int, drawn) -> dict:
    """Measure every composer-drawn text against the floor, AFTER the
    provider's downscale.

    ``drawn`` is a sequence of (role, sample_text, font_size). Returns the
    record that goes into the package manifest; the caller refuses on
    ``below_floor``. Nothing here asserts legibility — every number is a
    measurement of the text that will actually be transmitted.
    """
    scale = provider_downscale(sheet_long_edge)
    texts = []
    for role, sample, size in drawn:
        glyph = _glyph_px(sample, size)
        texts.append({"role": role, "font_size": size,
                      "glyph_px": glyph,
                      "effective_px": round(glyph * scale, 2)})
    worst = min((t["effective_px"] for t in texts), default=0.0)
    return {
        "provider_long_edge_limit": PROVIDER_LONG_EDGE_LIMIT,
        "sheet_long_edge": sheet_long_edge,
        "provider_downscale": round(scale, 4),
        "floor_effective_px": SHEET_TEXT_MIN_EFFECTIVE_PX,
        "texts": texts,
        "worst_effective_px": worst,
        "below_floor": [t["role"] for t in texts
                        if t["effective_px"] < SHEET_TEXT_MIN_EFFECTIVE_PX],
    }


def view_annotation_legibility(view_path: str, panel_scale: float,
                               sheet_long_edge: int) -> dict:
    """The measured fate of text BAKED INTO a view PNG by the renderer.

    RBV-4's live review reported the ``bounds_dimensions`` annotations
    unreadable, and this is why: the renderer draws them with PIL's default
    bitmap font, the sheet then fits the view into a panel, and the provider
    downscales the whole sheet. Two reductions compound. This measurement is
    recorded as a KNOWN limitation — the composer supersedes those
    annotations with legible text rather than silently leaving them.
    """
    with Image.open(view_path) as img:
        view_size = img.size
    default_glyph = 8   # PIL's built-in bitmap face, measured
    scale = provider_downscale(sheet_long_edge)
    return {
        "view_pixel_size": list(view_size),
        "renderer_font": "PIL default bitmap face (no truetype face given)",
        "baked_glyph_px": default_glyph,
        "panel_scale": round(panel_scale, 4),
        "provider_downscale": round(scale, 4),
        "effective_px": round(default_glyph * panel_scale * scale, 2),
        "superseded_by": ("the composer draws the same contract dimensions "
                          "from the render manifest at a measured, "
                          "above-floor size; the baked annotations are left "
                          "in the frozen render evidence untouched"),
    }


def standard_status(name: str) -> dict:
    """Live-quoted schema + status of a camera/lighting proposal — the
    package reflects an owner approval the moment it is recorded, and
    never claims it earlier."""
    data = json.load(open(os.path.join(_RBV_DOCS, name)))
    return {"schema": data["schema"], "status": data["status"],
            "source": f"docs/visual_quality/rbv/{name}"}


def load_validation_render(render_dir: str, *,
                           view_files: dict | None = None) -> dict:
    """Hash-verified load of an RBV-2B render directory.

    ``view_files`` rebinds view names to renamed files; a rebinding that
    does not reproduce the recorded decoded-pixel hash refuses.
    """
    findings = []
    manifest_path = os.path.join(render_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise Rbv3Refusal([f"{RBV3_RENDER_MANIFEST_MISSING}:{render_dir}"])
    manifest = json.load(open(manifest_path))
    if manifest.get("schema") != RENDER_MANIFEST_SCHEMA:
        raise Rbv3Refusal([f"{RBV3_RENDER_SCHEMA_MISMATCH}:"
                           f"{manifest.get('schema')}"])
    # §AL3(a) — the honesty fields are required, not defaulted. See
    # REQUIRED_RENDER_MANIFEST_FIELDS for why each absence is a claim.
    missing = [f for f in REQUIRED_RENDER_MANIFEST_FIELDS
               if not manifest.get(f)]
    missing += [f for f in REQUIRED_RENDER_MANIFEST_LISTS
                if not isinstance(manifest.get(f), list)]
    for field in REQUIRED_RENDER_MANIFEST_MAPS:
        value = manifest.get(field)
        if not isinstance(value, dict) or not value:
            missing.append(field)
    if isinstance(manifest.get("dimensions"), dict):
        # NB: written without a defaulted read on purpose. The first
        # version of this very check used one, and the gate reported it
        # as a new fallback occurrence in the function whose fallbacks
        # this commit exists to remove.
        dims = manifest["dimensions"]
        missing += [f"dimensions.{f}" for f in REQUIRED_DIMENSION_FIELDS
                    if f not in dims or not dims[f]]
    if missing:
        raise Rbv3Refusal([f"{RBV3_RENDER_MANIFEST_INCOMPLETE}:{f}"
                           for f in missing])
    resolved, rebound = {}, {}
    for view, recorded_name in manifest["views"].items():
        name = (view_files or {}).get(view, recorded_name)
        path = os.path.join(render_dir, name)
        if not os.path.isfile(path):
            findings.append(f"{RBV3_VIEW_MISSING}:{view}:{name}")
            continue
        # §AL3(a). This was a defaulted two-step lookup into pixel_hashes,
        # guarded by a truthiness test, so a view with no recorded hash
        # SKIPPED the decoded-pixel check that is this module's entire
        # stated guarantee and was returned as verified. Not hypothetical:
        # measured 2026-08-20, three views across two committed evidence
        # directories (2026-08-04 measurement_overlay; _v2 that plus
        # material_reference_preview) resolve on disk with no recorded
        # hash and load unverified today. An unhashed view is now a
        # finding, and the comparison is unconditional.
        expected = manifest["pixel_hashes"].get(view)
        if not expected:
            findings.append(f"{RBV3_VIEW_HASH_ABSENT}:{view}:{name}")
            continue
        if pixel_hash(path) != expected:
            findings.append(f"{RBV3_VIEW_HASH_MISMATCH}:{view}:{name}")
            continue
        resolved[view] = path
        if name != recorded_name:
            rebound[view] = name
    if findings:
        raise Rbv3Refusal(findings)
    return {"manifest": manifest, "manifest_sha256":
            _file_sha256(manifest_path), "resolved_views": resolved,
            "rebound": rebound}


def _validate_references(references) -> list[dict]:
    findings, out = [], []
    for i, ref in enumerate(references or []):
        klass = ref.get("evidence_class")
        if klass not in REFERENCE_EVIDENCE_CLASSES:
            findings.append(f"{RBV3_REFERENCE_CLASS_INVALID}:{klass}")
            continue
        if not os.path.isfile(ref.get("path", "")):
            findings.append(f"{RBV3_REFERENCE_FILE_MISSING}:"
                            f"{ref.get('path')}")
            continue
        out.append({"path": ref["path"], "evidence_class": klass,
                    "caption": ref.get("caption", ""),
                    "disclaimer": REFERENCE_DISCLAIMER})
    if findings:
        raise Rbv3Refusal(findings)
    return out


def _fit(img, max_w, max_h):
    """Uniform scale only — aspect ratio is never distorted."""
    s = min(max_w / img.width, max_h / img.height, 1.0)
    return img.resize((max(1, int(img.width * s)),
                       max(1, int(img.height * s))), Image.LANCZOS)


def _panel(board, draw, img, x, y, max_w, max_h, title, colour):
    img = _fit(img.convert("RGB"), max_w, max_h)
    board.paste(img, (x, y + 48))
    draw.rectangle([x - 3, y + 45, x + img.width + 3,
                    y + 48 + img.height + 3], outline=colour, width=4)
    font = _font(30)
    while title and draw.textlength(title, font=font) > img.width + 40:
        title = title[:-2].rstrip() + "…"
    draw.text((x, y), title, font=font, fill=colour)
    return img.width


def _compose_sheet(subject_id, render, references, camera, lighting,
                   out_path):
    manifest = render["manifest"]
    views = render["resolved_views"]
    grey = (90, 90, 92)
    red = (179, 69, 79)
    blue = (24, 60, 130)
    W = 3840
    board = Image.new("RGB", (W, 6200), (247, 245, 242))
    draw = ImageDraw.Draw(board)
    draw.text((60, 40), "RBV-3 STANDARD VISUAL REVIEW PACKAGE — "
                        f"{subject_id}", font=_font(60), fill=(30, 30, 34))
    # §AL3(a): both were defaulted to blank. banners[0] is the red first line
    # and is the §1 caveat governing how every image below it may be read;
    # a blank one is a validation render presented with nothing saying so.
    # load_validation_render now refuses a manifest missing either.
    banners = [
        manifest["statement"],
        f"camera: {camera['schema']} [{camera['status']}] · lighting: "
        f"{lighting['schema']} [{lighting['status']}]",
        f"reference availability: {manifest['reference_availability']}",
        DECISION_CHANNEL,
    ]
    for i, line in enumerate(banners):
        draw.text((60, 130 + i * 40), line, font=_font(28),
                  fill=red if i == 0 else (90, 70, 60))
    y = 330
    x = 60
    row_h = 0
    for view in [v for v in CANONICAL_VIEW_ORDER if v in views] + \
            sorted(v for v in views if v not in CANONICAL_VIEW_ORDER):
        img = Image.open(views[view])
        w = int(1100 * img.width / img.height) if img.height else 1100
        if x + min(w, 900) + 60 > W:
            x = 60
            y += row_h + 140
            row_h = 0
        pw = _panel(board, draw, img, x, y, 900, 1100,
                    f"{view} — NEUTRAL GEOMETRY VALIDATION", grey)
        x += pw + 60
        row_h = max(row_h, min(1100, img.height))
    y += row_h + 160
    # mode B absence is VISIBLE, never silent
    draw.rectangle([60, y, 1400, y + 360], outline=red, width=5)
    draw.text((90, y + 30), "CLIENT PRESENTATION — ABSENT (BLOCKED)",
              font=_font(40), fill=red)
    for i, reason in enumerate(PRESENTATION_ABSENT_REASONS):
        draw.text((90, y + 100 + i * 44), reason, font=_font(30),
                  fill=(140, 70, 70))
    head, _, tail = TWO_MODE_RULE.partition("; ")
    for i, line in enumerate((head, tail)):
        draw.text((90, y + 188 + i * 38), line, font=_font(26),
                  fill=(110, 90, 80))
    # §11 measurements + warnings, verbatim from the render manifest
    mx = 1500
    draw.text((mx, y), "§11 MEASUREMENTS (render manifest, verbatim)",
              font=_font(36), fill=(30, 30, 34))
    # Required at the boundary (REQUIRED_RENDER_MANIFEST_MAPS), so this
    # is a read, not a fallback: the heading says "verbatim".
    meas = manifest["measurements"]
    # §S2: the bounds_dimensions view carries the contract dimensions in
    # renderer-baked text that does not survive the provider's downscale
    # (measured: see view_annotation_legibility). The same figures are
    # authoritative in the manifest, so they are drawn HERE at a measured,
    # above-floor size rather than left illegible inside the panel.
    # §AL3(a): `dims` defaulted to {} silently OMITTED this restatement —
    # leaving the renderer-baked annotations, measured illegible after the
    # provider downscale, as the only dimension figures on the sheet — and
    # `side_depth_mm or front_width_mm` printed the width under a D label.
    # Both fields are now required at load, so both reads are direct.
    dims = manifest["dimensions"]
    lines = [
        f"CONTRACT DIMENSIONS  H {dims['height_mm']}mm · "
        f"W {dims['front_width_mm']}mm · D {dims['side_depth_mm']}mm"
        "   (legible restatement of the bounds_dimensions annotations)"]
    lines.append(f"expected_mm_per_px: {meas.get('expected_mm_per_px')}")
    for view in ("front", "side", "top", "closure_detail"):
        entry = meas.get(view)
        if isinstance(entry, dict):
            facts = {k: v for k, v in entry.items() if k != "bounds_px"}
            lines.append(f"{view}: {json.dumps(facts, sort_keys=True)}"
                         [:160])
    # §AL3(a): defaulted to [], an ABSENT key rendered as the positive
    # assertion "warnings: none" in the same grey used for a genuinely
    # clean render — a missing key shown to the reviewer as a clean bill
    # of health. Required at load; "none" now means measured none.
    warnings = manifest["warnings"]
    lines.append("warnings: " + (", ".join(warnings) if warnings
                                 else "none"))
    for i, line in enumerate(lines):
        emphasis = line.startswith("CONTRACT DIMENSIONS")
        draw.text((mx, y + 60 + i * 40), line,
                  font=_font(30 if emphasis else 26),
                  fill=(30, 30, 34) if emphasis else
                  ((60, 60, 64) if not line.startswith("warnings")
                   or not warnings else red))
    y += 460
    if references:
        x = 60
        for ref in references:
            pw = _panel(board, draw, Image.open(ref["path"]), x, y,
                        900, 1100,
                        f"{ref['evidence_class']} — {ref['caption']}"[:70],
                        blue)
            x += pw + 60
        draw.text((60, y + 1170), REFERENCE_DISCLAIMER, font=_font(28),
                  fill=red)
        y += 1260
    # smallest text on the sheet: raised 24 -> 26 so it clears the §S2
    # floor with margin rather than by 0.07px
    draw.text((60, y), f"source: RBV-2B manifest sha256 "
                       f"{render['manifest_sha256'][:16]} · "
                       f"{manifest['blender_version']} · "
                       f"{manifest['render_engine']}",
              font=_font(26), fill=grey)
    board = board.crop((0, 0, W, y + 80))
    board.save(out_path)
    return sheet_legibility(max(board.size), (
        ("title", f"RBV-3 STANDARD VISUAL REVIEW PACKAGE — {subject_id}", 60),
        # §AL3(a) — THE GATING OCCURRENCE, and the one that made the
        # others reachable. This sample used to carry an `or` substitute
        # supplying the literal word statement whenever the real banner
        # was EMPTY, giving a 20-glyph-pixel measurement of text nobody
        # drew. (The old expression is not quoted here: a source-string
        # guard below asserts its absence, and quoting it in a comment
        # would satisfy the search and disarm the guard.) So
        # the §S2 floor was cleared at 13.42 effective px by a string the
        # composer never drew: measured, `_glyph_px("", 28) == 0` against
        # a floor of 12.0, so the substitution converted a fail-closed
        # refusal into a committed package certifying a missing
        # disclaimer as legible. The refusal at build_review_package
        # precedes the json.dump, so removing this default is what stops
        # the empty statement shipping at all. The sample is now the text
        # that will actually be transmitted, which is what the
        # sheet_legibility docstring always claimed it was.
        ("banner", banners[0], 28),
        ("panel_title", "bounds_dimensions — NEUTRAL GEOMETRY VALIDATION",
         30),
        ("mode_b_heading", "CLIENT PRESENTATION — ABSENT (BLOCKED)", 40),
        ("mode_b_reason", PRESENTATION_ABSENT_REASONS[0], 30),
        ("mode_b_rule", TWO_MODE_RULE[:60], 26),
        ("measurements_heading",
         "§11 MEASUREMENTS (render manifest, verbatim)", 36),
        ("contract_dimensions", lines[0] if dims else "CONTRACT DIMENSIONS",
         30),
        ("measurement_line", "expected_mm_per_px: 0.05819", 26),
        ("source_line", "source: RBV-2B manifest sha256 0123456789abcdef",
         26),
    ))


def build_review_package(render_dir: str, out_dir: str, *,
                         subject_id: str, created_at: str,
                         view_files: dict | None = None,
                         references=None, note: str = "") -> dict:
    """Assemble the standard package into ``out_dir`` and return the
    ``rbv3_review_package/1.0`` manifest (also written alongside)."""
    render = load_validation_render(render_dir, view_files=view_files)
    refs = _validate_references(references)
    camera = standard_status("camera_standard_proposal.json")
    lighting = standard_status("lighting_standard_proposal.json")
    os.makedirs(out_dir, exist_ok=True)

    manifest = render["manifest"]
    packaged_views = {}
    for view, src in render["resolved_views"].items():
        packaged_views[view] = {
            "source_file": os.path.basename(src),
            "pixel_hash": manifest["pixel_hashes"][view],
        }
    packaged_refs = []
    for i, ref in enumerate(refs):
        dst_name = f"reference_{i}.png"
        shutil.copyfile(ref["path"], os.path.join(out_dir, dst_name))
        packaged_refs.append({"file": dst_name,
                              "evidence_class": ref["evidence_class"],
                              "caption": ref["caption"],
                              "disclaimer": ref["disclaimer"]})

    sheet_path = os.path.join(out_dir, SHEET_NAME)
    legibility = _compose_sheet(subject_id, render, refs, camera, lighting,
                                sheet_path)
    # §S2 fail-closed: a package whose own text cannot survive the
    # reviewing provider's downscale is not a review surface. Refusing
    # beats shipping a sheet the reviewer cannot read — RBV-4 spent
    # budgeted calls on exactly that.
    if legibility["below_floor"]:
        raise Rbv3Refusal(
            [f"{RBV3_SHEET_TEXT_ILLEGIBLE}:{role}:"
             f"{[t['effective_px'] for t in legibility['texts'] if t['role'] == role][0]}"
             f"px<{SHEET_TEXT_MIN_EFFECTIVE_PX}"
             for role in legibility["below_floor"]])
    bounds_view = render["resolved_views"].get("bounds_dimensions")
    if bounds_view:
        with Image.open(bounds_view) as _bv:
            panel_scale = min(900 / _bv.width, 1100 / _bv.height, 1.0)
        legibility["renderer_baked_annotations"] = \
            view_annotation_legibility(bounds_view, panel_scale,
                                       legibility["sheet_long_edge"])

    package = {
        "schema": SCHEMA,
        "subject_id": subject_id,
        "created_at": created_at,
        # §AL3(a): PERSISTED into the committed package manifest, rendered
        # on the dashboard, and copied again into the RBV-4 review record —
        # three surfaces on which a defaulted blank reads as a package that
        # simply has no scope statement. Required at load; read directly.
        "statement": manifest["statement"],
        "note": note,
        "decision_channel": DECISION_CHANNEL,
        "owner_review": {"status": "QUEUED_PENDING_OWNER_REVIEW",
                         "granted": False},
        "camera_standard": camera,
        "lighting_standard": lighting,
        "modes": {
            MODE_GEOMETRY_VALIDATION: {
                "source_render_manifest": {
                    "schema": manifest["schema"],
                    "sha256": render["manifest_sha256"],
                    "fixture_id": manifest.get("fixture_id"),
                    "authority_class": manifest.get("authority_class"),
                },
                "views": packaged_views,
                "view_source_dir": _repo_relative(render_dir),
                "view_storage_policy": VIEW_STORAGE_POLICY,
                "view_rebinding": render["rebound"],
                "measurements": manifest["measurements"],
                # §AL3(a): these two are persisted, then rendered by
                # templates/dashboard/rbv3_review_packages.html as
                # `|default:"none"` inside the red warn cell — so an
                # absent upstream key became the owner-facing string
                # "none" under the heading "§11 warnings", a displayed
                # assertion that the render raised nothing. Required at
                # load as PRESENT lists, so [] now means measured-empty.
                "warnings": manifest["warnings"],
                "uncertainty": manifest["uncertainty"],
                "reference_availability": manifest["reference_availability"],
            },
            MODE_CLIENT_PRESENTATION: {
                "status": "ABSENT_BLOCKED",
                "reasons": list(PRESENTATION_ABSENT_REASONS),
                "rule": TWO_MODE_RULE,
            },
        },
        "references": packaged_refs,
        "legibility": legibility,
        "contact_sheet": {"file": SHEET_NAME,
                          "pixel_hash": pixel_hash(sheet_path),
                          # the sheet's pixels depend on this exact face:
                          # recorded so a font change reads as a cause, not
                          # as mystery drift
                          "font": {"path": _FONT,
                                   "sha256": _file_sha256(_FONT)[:16]}},
    }
    json.dump(package, open(os.path.join(out_dir, MANIFEST_NAME), "w"),
              indent=1)
    return package
