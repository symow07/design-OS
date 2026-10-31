"""Explicit native-Illustrator handoff generation (Phase 2A-8 §14/§15).

Builds the handoff package for a completed composition WITHOUT touching the
task's state, the accepted artwork files or the legacy preview emitter. The
document is recomposed deterministically from persisted state (the job's
validated input_json, the carton's map front on its record, the panel copy it
was made with) by the composer the carton's own design .ai is made by, so the
package is the carton's own drawing — [E5b, the owner's Q2, approved with the
clean-up list at b5892f9] a carton has one engine: the direction's style is
never drawn in its place, and a carton whose front no map draws is refused.

Output modes stay side by side:
    PDF_COMPATIBLE_AI_PREVIEW      — the existing deliverables (unchanged)
    ILLUSTRATOR_JSX_NATIVE_HANDOFF — this package, generated explicitly
"""
from __future__ import annotations
from apps.pipeline.targets.container import archetypes as _declared

import os

from django.conf import settings

MODE_PREVIEW = "PDF_COMPATIBLE_AI_PREVIEW"
MODE_NATIVE = "ILLUSTRATOR_JSX_NATIVE_HANDOFF"


class HandoffError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


#: E5b — the owner's Q2, approved with the clean-up list (transcribed at b5892f9): "rebuild 'Prepare the Illustrator
#: package' on the map-front drawing", so a carton has one engine. A carton whose front no map of its concept draws has
#: no package: refused by this name before anything is composed or written, and nothing is drawn in its place.
HANDOFF_NO_MAP_FRONT = "HANDOFF_NO_MAP_FRONT"
#: [E5b] the package's front measured otherwise than the carton's own design file measured its front — said beside the
#: package's checks, never silently: the record moved after the carton was made
HANDOFF_FRONT_NOT_THE_CARTONS = "HANDOFF_FRONT_NOT_THE_CARTONS"
NO_MAP_FRONT_WORDS = ("this carton's front was not drawn from its concept's map — no map of its chosen picture is on "
                      "its record — so no Illustrator package is made: the package is built only from the drawing the "
                      "carton itself is made from, and nothing else is drawn in its place")


def carton_map_front(output) -> dict | None:
    """[E5b] The carton's front as its own concept's map draws it, read through the one door the carton itself is drawn
    through (``ARIAAgent.resume_after_dimensions``: its target's ``carton_map_front``) — the map and its shapes kept on
    the output. Nothing paid runs: a shape traced again where the tracer's numbers moved costs nothing and is kept as the
    drawing keeps it. None where no map of its picture is on record, or its target reads none."""
    from apps.pipeline.targets import get_target
    task = output.task
    return get_target(task.design_target).carton_map_front(task, output)


#: [E5b] what a carton document's front is when its concept's map draws it (``apps/ire/compose.py``,
#: ``compose_components_graph``): the front panel's ground, the map's own drawing, and the mark set on that front
_FRONT_NODES = ("panel-front", "Map front", "logo-front")


def front_digest(doc) -> str | None:
    """[E5b] The sha256 of a carton document's front as its concept's map draws it — the nodes ``_FRONT_NODES`` names,
    each whole, as canonical JSON — or None where the document draws no front from a map. Two documents with one digest
    print one front."""
    import hashlib
    import json
    found = {}
    for node, _parent in doc.walk():
        name = node.name                       # every graph node carries one
        if name in _FRONT_NODES and name not in found:
            found[name] = node.model_dump(mode="json")
    if "Map front" not in found:
        return None
    return hashlib.sha256(json.dumps([found.get(n) for n in _FRONT_NODES], sort_keys=True,
                                     ensure_ascii=True).encode()).hexdigest()


def _carton_document(params, coords, panel_info, map_front, turn_faces: bool = False):
    """[E5b] The carton's design document composed as its own design .ai is (``generate_exports``'s map-front call of
    ``compose_components_graph``, the one ``resume_after_dimensions`` reaches): the front from its concept's map, on the
    map's own ground; every other panel ruled; the house mark through its one switch; the panel copy the carton was made
    with. Returns ``(the document, the mark's raster to ship beside it, or None when the mark is drawn as paths)``."""
    from apps.ire import brand_mark as _brand_mark
    from apps.ire.compose import compose_components_graph
    house = _brand_mark.house_mark()
    doc = compose_components_graph(
        coords, logo_path=house["png"],
        product_name=params.metadata.product_name,          # both required strings on the schema
        subtitle=params.metadata.product_type,
        panel_info=panel_info, map_front=map_front,
        safe_margin_mm=params.print_settings.safe_margin_mm,
        turn_faces=turn_faces,                                # [his goal of 2026-10-13, (2)] a box lying flat
        **({"tint": map_front["ground"]} if map_front.get("ground") else {}),
        **_brand_mark.master_kwargs(house["master"]))
    return doc, (house["png"] if house["master"] is None else None)


def generate_native_handoff(output, user, *, run_illustrator: bool = False
                            ) -> dict:
    """Build the package under the job's export dir; record spec['handoff'].

    [E5b — the owner's Q2, approved with the clean-up list (transcribed at b5892f9).] The package is the carton's own
    drawing: its Design Graph is composed by the composer the carton's design .ai is, from the map front on its record
    (``carton_map_front``) — the direction's style is never drawn in its place (it was, by
    ``compose_vector_art_graph``, with no map front). A carton whose front no map draws is refused by name
    (``HANDOFF_NO_MAP_FRONT``) before anything is composed or written.

    ``run_illustrator``: attempt real §11 execution when the environment
    has Illustrator; otherwise the manifest carries
    ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED.
    """
    import json

    from apps.dielines.geometry.engine import calculate_dieline
    from apps.dielines.services.export_service import job_export_dir
    from apps.dielines.validators.schema import DielineInputJSON
    # The §AU5(4) gate below is the THIRD copy of this closure, and the first
    # two both carried their own import. This one did not, and no static check
    # caught it: the names resolve at CALL time, so the module imports, the
    # file compiles, and grep confirms the gate sits ahead of the writer. It
    # was `NameError: name 'brand_string_report' is not defined` under a real
    # invocation that found it — which is precisely §AA's point that a guard
    # nobody has watched fire is not evidence of anything. The broken version
    # failed CLOSED, but it failed closed by CRASHING, on the clean path too.
    from apps.ire.brand_string_runtime import (
        BRAND_STRING_ARTEFACT_WITHHELD, brand_string_report)
    from apps.ire.compose import CARTON_MAP_FRONT, FRONT_TYPE_KEY
    from apps.ire.handoff.package import build_handoff_package, validate_handoff

    job = output.dieline_job
    if job is None or not job.input_json:
        raise HandoffError("HANDOFF_NO_COMPOSITION",
                           "no composed dieline job exists for this output")
    task = output.task
    # [E5b] the front first, by the carton's own door — read before the record, which a shape traced again is kept on
    map_front = carton_map_front(output)
    if map_front is None:
        raise HandoffError(HANDOFF_NO_MAP_FRONT, NO_MAP_FRONT_WORDS)
    spec_sheet = output.spec_sheet or {}

    params = DielineInputJSON(**job.input_json)
    coords = calculate_dieline(params)
    doc, logo_asset = _carton_document(params, coords, spec_sheet.get("panel_info"), map_front,
                                       turn_faces=job.input_json.get("orientation") == "flat")   # [his goal of 2026-10-13, (2)]
    digest = front_digest(doc)
    if digest is None:                     # a die with no front panel for the map to be drawn on
        raise HandoffError(HANDOFF_NO_MAP_FRONT, NO_MAP_FRONT_WORDS)

    # §AU5(4)/§AU8(e) — THE THIRD LEAK, and it was found by grepping for the
    # SHAPE rather than by working the container brief. `build_handoff_package`
    # below writes the .jsx and assets, `run_jsx` executes them, and
    # `validate_handoff` runs after both: the same inversion as the container
    # handoff, in the DIELINE path, which no part of the §AU order pointed at.
    #
    # It is closed here rather than registered as backlog because the composer
    # two lines up takes `product_name` and `subtitle` directly into the
    # document — measured, not assumed — so this path can carry a provisional
    # descriptor to a printable proof exactly like the other two. A close report
    # claiming "fail closed on every path" with a known third path open would be
    # a false claim, and the false claim is worse than the wider diff.
    brand_strings = brand_string_report(doc)
    if not brand_strings["clean"]:
        raise HandoffError(
            BRAND_STRING_ARTEFACT_WITHHELD,
            "the composed dieline artwork carries provisional brand copy, so "
            "no handoff package is written and nothing is handed to "
            "Illustrator: " + "; ".join(brand_strings["codes"]))

    blockers = []
    if (spec_sheet.get("confirmed_font") or {}).get("production_blocker"):
        blockers.append(spec_sheet["confirmed_font"]["production_blocker"])
    if spec_sheet.get("output_intent_missing"):
        blockers.append("MISSING_OUTPUT_INTENT")

    out_dir = job_export_dir(job.id) / "handoff"
    package = build_handoff_package(
        doc, str(out_dir), task_id=task.pk,
        geometry_hash=str((spec_sheet.get("structure_presentation") or {})
                          .get("geometry_hash", "")),
        production_blockers=tuple(blockers),
        # [the owner's second answer of 2026-09-25: a mark drawn from the master is paths — no raster ships]
        logo_asset=logo_asset)

    illustrator_summary = None
    execution_state = "ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED"
    if run_illustrator:
        from apps.ire.handoff.illustrator_exec import run_jsx
        illustrator_summary = run_jsx(package["paths"]["jsx"])
        if illustrator_summary.get("executed"):
            execution_state = ("EXECUTED_"
                               + str(illustrator_summary.get("status",
                                                             "UNKNOWN")))
        else:
            illustrator_summary = None
    codes = validate_handoff(doc, package["graph"],
                             illustrator_summary=illustrator_summary)
    # [E5b] the front set as the carton's own design file set its front (FRONT_TYPE_KEY, written where the carton
    # was composed) — else said beside the package's checks, never silently: the record moved after it was made
    if json.loads(json.dumps(doc.metadata.get(FRONT_TYPE_KEY))) != spec_sheet.get(FRONT_TYPE_KEY):
        codes.append(HANDOFF_FRONT_NOT_THE_CARTONS + ": the package's front is set otherwise than the carton's "
                     "own design file — make the design again before the package is used")

    graph = package["graph"]
    relative = f"dielines/{job.id}/handoff"
    _struct = dict(getattr(job, "structure_selection", None) or {})
    spec_sheet["handoff"] = {
        "mode": MODE_NATIVE,
        # 2A-9E §3: the structural version is never omitted from the manifest
        "template": _struct.get("template_id") or job.template_type,
        "template_version": _struct.get("template_version"),
        "emitter_version": package["manifest"]["emitter_version"],
        "schema_version": package["manifest"]["handoff_graph_schema"],
        "files": {"jsx": f"{relative}/design_handoff.jsx",
                  "graph": f"{relative}/design_graph.json",
                  "manifest": f"{relative}/handoff_manifest.json"},
        "hashes": package["hashes"],
        "layer_count": len(graph["root_layers"]),
        "group_count": sum(len(groups)
                           for groups in graph["layer_tree"].values()),
        "swatch_count": len(graph["process_swatches"]),
        "spot_count": len(graph["spot_swatches"]),
        "text_run_count": graph["object_census"].get("text", 0),
        "raster_fallback_count": graph["object_census"].get("image", 0),
        "fonts": graph["fonts"],
        "execution_state": execution_state,
        "validation_codes": codes,
        "production_blockers": blockers,
        # [E5b] what the package is drawn from — the carton's own map-front drawing — and its front's digest
        "drawn_from": CARTON_MAP_FRONT,
        "front_digest": digest,
        "support_note": "Adobe Illustrator 2024+ (ExtendScript); fonts are "
                        "references — install the listed faces before "
                        "running the script",
    }
    output.spec_sheet = spec_sheet
    output.save(update_fields=["spec_sheet"])

    from apps.pipeline.models import AgentLog
    AgentLog.objects.create(
        task=task, agent_name="ARIA", actor=user,
        action=(f"Native Illustrator handoff package generated (job "
                f"{job.id}) — graph {package['hashes']['graph'][:12]}…, "
                f"{execution_state}"),
        payload={"hashes": package["hashes"], "codes": codes},
    )
    return spec_sheet["handoff"]


__all__ = ["generate_native_handoff", "HandoffError", "MODE_PREVIEW",
           "MODE_NATIVE"]


#: §BH70(1), item 6 of the list the owner was sent: the two stops a face form's hand-off can make, by name
HANDOFF_NEEDS_THE_CONCEPTS_READING = "HANDOFF_NEEDS_THE_CONCEPTS_READING"
HANDOFF_FACE_NOT_DERIVABLE = "HANDOFF_FACE_NOT_DERIVABLE"


def _confirmed_profile(spec: dict) -> dict:
    """The confirmed profile as the governed resume hands it on: the record's archetype and variant, the cap from its
    `cap_type` field, the body's height, width and depth, the neck ratio — nothing it does not hold."""
    record = spec.get("container_profile/1.0") or {}
    fields = record.get("fields") or {}

    def value(name):
        return (fields.get(name) or {}).get("value")
    held = {"archetype": record.get("archetype"), "variant": record.get("variant"), "cap_style": value("cap_type"),
            "height_mm": value("body_height_mm"), "width_mm": value("body_width_mm"),
            "depth_mm": value("body_depth_mm"), "neck_ratio": value("neck_ratio")}
    return {k: v for k, v in held.items() if v not in (None, "")}


def _face_handoff_document(output, spec: dict):
    """§BH70(1), item 6: A FACE FORM'S HAND-OFF IS THE FACE PRODUCTION DREW. The hand-off recomposed every form through
    the ruled front — name, rule, one line — which on a compact is a bottle's front label laid over its lid, while his
    §BH66(a) (LIVE) gave a face "the concept's own arrangement". It is derived here exactly as `reconstruct_container`
    and the design loop derive it (`targets.container.face_form_inputs` / `draw_face_form`), with a reader that returns
    only the concept reading the record already holds: the hand-off never pays for a reading, and says so by name when
    the record holds none."""
    from apps.pipeline.services import concept_layout
    from apps.pipeline.targets import container as C

    def reading_held(task, spec, **kw):
        held, why = concept_layout.cached(spec, kw.get("image_path"))
        if held is None:
            raise HandoffError(HANDOFF_NEEDS_THE_CONCEPTS_READING, (
                "a lid is drawn from the concept's own arrangement, read from its picture, and this design's picture "
                "has not been read (%s) — the hand-off never pays for a reading; reconstructing the design on the "
                "governed path reads it" % why))
        return held
    try:
        inputs = C.face_form_inputs(output.task, output, _confirmed_profile(spec), read_layout=reading_held)
    except HandoffError:
        raise
    except ValueError as exc:                              # the derivation's own refusals, each already by name
        raise HandoffError(HANDOFF_FACE_NOT_DERIVABLE,
                           "the lid's face could not be derived as it was drawn: %s" % exc) from exc
    doc, _applied = C.draw_face_form(inputs)
    return doc


def generate_container_native_handoff(output, user, *,
                                      run_illustrator: bool = False) -> dict:
    """2B-4: the explicit Product Container handoff package. Recomposes the
    container Document DETERMINISTICALLY from the persisted confirmed records
    (no provider), builds the package, and records spec['container_handoff'].
    Human visual authority travels with the manifest and is never cleared by
    a successful execution."""
    from apps.ire import container_motif as cm
    from apps.ire.brand_string_runtime import (
        BRAND_STRING_ARTEFACT_WITHHELD, brand_string_report)
    from apps.ire.compose_container import compose_container_graph
    from apps.ire.container_production_readiness import (
        build_readiness, human_design_acceptance)
    from apps.ire.front_hierarchy import descriptor_for, ruled_front_hierarchy
    from apps.ire.handoff.container_adapter import (
        build_container_handoff_package, validate_container_handoff)
    from apps.pipeline.services.selected_concept import load_selected_variation
    from apps.pipeline.targets.container.silhouettes import (
        ContainerProfile, build_backbone)

    task = output.task
    spec = output.spec_sheet or {}
    profile = spec.get("container_profile/1.0") or {}
    zones = (spec.get("container_decoration_zones/1.0") or {}).get("zones") or []
    if not profile or not zones or not spec.get("container_reconstruction"):
        raise HandoffError("HANDOFF_NO_COMPOSITION",
                           "no confirmed native container reconstruction "
                           "exists for this output")
    fields = profile.get("fields") or {}

    def _fv(name, default=None):
        v = (fields.get(name) or {}).get("value")
        return v if v is not None else default

    def _closure_word(value):
        """The confirmed closure's first word ("dropper (glass pipette)" -> "dropper"), or None."""
        words = str(value).split() if value else []
        return words[0] if words else None

    variation = load_selected_variation(task, output.approved_image) \
        if output.approved_image else None
    motif_spec = cm.build_motif_spec(
        variation if variation and variation.get("verified") else None,
        {"fields": {}}, zones, profile)
    backbone = build_backbone(ContainerProfile(
        # §BH61(a): the confirmed profile's own archetype, or a refusal — never a bottle by default.
        archetype=_declared.resolve(
            profile.get("archetype"),
            looked_in=["the confirmed container_profile/1.0 record"]),
        # §BH65(e): these five fell back to a BOTTLE's parts — "cylindrical", 40 x 110, a 0.42 neck and a screw
        # cap — so a compact confirmed without them was handed off as a bottle's variant and closure. Each now
        # carries what the confirmed record holds, None when it holds nothing; `build_backbone` draws a missing
        # dimension from THIS form's own declared nominal, and a form without a neck is never given one.
        variant=profile.get("variant"),
        width_mm=_fv("body_width_mm"),
        height_mm=_fv("body_height_mm"),
        neck_ratio=_fv("neck_ratio"),
        cap_style=_closure_word(_fv("cap_type"))))
    transparency = None
    opacity_text = f'{_fv("body_opacity", "")} {_fv("body_transparency", "")}'
    colors = spec.get("colors") or {}
    if "transparent" in opacity_text.lower():
        transparency = {"state": "TRANSPARENT",
                        "product_color": colors.get("product", "#F2C4CE")}
    product_name = spec.get("product_name", "")
    # THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    # switch the mark to it so gold foil can print." The house mark through its one switch (apps/ire/brand_mark.py)
    from apps.ire import brand_mark as _brand_mark
    _house = _brand_mark.house_mark()
    # §BB7(c) at OWNER_BLOCKER_CLEARANCE.md:10559 — the second of the two call
    # sites the owner named. Same ruling, same tiers, same decoration trade as
    # the container target's; see apps/ire/front_hierarchy.py for why the
    # content is built there and the plumbing stays here.
    if _declared.is_face(backbone.archetype):
        # §BH70(1), item 6: a face form hands off the face production drew — never the ruled front a bottle's label gets
        doc = _face_handoff_document(output, spec)
    else:
        doc = compose_container_graph(
            backbone, product_name=product_name,
            name_lines=[product_name] if product_name else [],
            zones=zones, native=True, motif_spec=motif_spec, colors=colors,
            transparency=transparency,
            # §BH65(b)1: this product's own descriptor, the same word the
            # container target printed — never a constant.
            hierarchy_lines=ruled_front_hierarchy(
                product_name, descriptor=descriptor_for(spec, task.product)),
            # [the owner's second answer of 2026-09-25: the house mark through its one switch — `png` is exactly
            # BRAND_LOGO_PATH-if-it-exists as before, `master` the approved vector master when one is on file]
            logo_path=_house["png"], **_brand_mark.master_kwargs(_house["master"]))

    # §AU5(4)/§AU8(e) — REFUSE BEFORE ANYTHING IS WRITTEN.
    #
    # The second leak of the same shape as the container target's, and the worse
    # of the two. `build_container_handoff_package` below WRITES the .jsx, the
    # manifest and the assets into MEDIA_ROOT, and `validate_container_handoff`
    # does not run until fourteen lines after that. With `run_illustrator` set,
    # `run_jsx` EXECUTES the package before the validation it has not yet
    # passed — the ordering is not merely late, it is inverted.
    #
    # `build_readiness(spec)` on the next line cannot stand in for this, and the
    # near-miss is worth naming: it reads codes PERSISTED on some earlier
    # document, while this reads the document composed nine lines up. A handoff
    # assembled from a fresh `compose_container_graph` and waved through by the
    # last run's readiness codes is precisely the gap §AV3 left open. The
    # document in front of you is the only one whose brand copy is knowable.
    #
    # Fail-closed idiom borrowed from HANDOFF_NO_COMPOSITION above rather than
    # invented: same exception, same shape, raised before the writer.
    brand_strings = brand_string_report(doc)
    if not brand_strings["clean"]:
        raise HandoffError(
            BRAND_STRING_ARTEFACT_WITHHELD,
            "the composed document carries provisional brand copy, so no "
            "handoff package is written and nothing is handed to Illustrator: "
            + "; ".join(brand_strings["codes"]))

    from apps.dashboard.owner_channel import preview_sha256
    picture = preview_sha256(output)[0]           # §BH71: his acceptance, read for the picture it names
    human = human_design_acceptance(spec, picture)
    readiness = build_readiness(spec, picture)
    out_dir = os.path.join(settings.MEDIA_ROOT, "container_handoff",
                           str(task.pk))
    # [the owner's second answer of 2026-09-25: the PNG ships as the linked asset only when the mark is the PNG]
    package = build_container_handoff_package(
        doc, spec, out_dir, task_id=task.pk, human_acceptance=human,
        # [the owner's answer of 2026-09-27: the printer's package carries the production notes beside what refuses]
        readiness_codes=(readiness["blocking_codes"] + readiness.get("production_notes", [])
                         + readiness.get("acceptance_warnings", [])),         # §BH71 (0a): what was never measured
        logo_asset=_house["png"] if _house["master"] is None else None)

    execution_state = "ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED"
    illustrator_summary = None
    if run_illustrator:
        from apps.ire.handoff.illustrator_exec import run_jsx
        illustrator_summary = run_jsx(package["paths"]["jsx"])
        if illustrator_summary.get("executed"):
            execution_state = ("EXECUTED_"
                               + str(illustrator_summary.get("status",
                                                             "UNKNOWN")))
    codes = validate_container_handoff(doc, package["graph"], spec)

    graph = package["graph"]
    relative = f"container_handoff/{task.pk}"
    spec["container_handoff"] = {
        "mode": "NATIVE_CONTAINER_HANDOFF",
        "schema_version": package["manifest"]["schema_version"],
        "emitter_version": package["manifest"]["emitter_version"],
        "handoff_label": package["manifest"]["handoff_label"],
        "files": {"jsx": f"{relative}/design_handoff.jsx",
                  "graph": f"{relative}/design_graph.json",
                  "manifest": f"{relative}/handoff_manifest.json"},
        "hashes": package["hashes"],
        "layer_count": len(graph["root_layers"]),
        "group_count": sum(len(g) for g in graph["layer_tree"].values()),
        "swatch_count": len(graph["process_swatches"]),
        "spot_count": len(graph["spot_swatches"]),
        "live_text_count": graph["object_census"].get("text", 0),
        "raster_fallback_count": graph["object_census"].get("image", 0),
        "decorative_raster_count": 0,
        "fonts": graph["fonts"],
        "surfaces": graph["panel_sublayers"],
        "zones": [z.get("zone_id") for z in zones],
        "separations": graph["separations_included"],
        "human_visual_acceptance_state": human.get("state", ""),
        "production_readiness_ready": readiness["ready"],
        "validation_codes": codes,
        "execution_state": execution_state,
        "explicit_only": True,
    }
    if illustrator_summary:
        spec["container_handoff"]["illustrator_summary"] = illustrator_summary
    output.spec_sheet = spec
    output.save(update_fields=["spec_sheet"])
    return spec["container_handoff"]
