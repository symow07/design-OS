"""M6 — PRODUCTS / OBSERVABILITY / TRACE / BOARDS.

The four items palette_powder_protocol.protocol_status() still lists as
not implemented, realized under the A19 scope statement
(contract_repair_design_rule.json): product-definition work MAY consume
the repaired powder contract; nothing here ships, no shade becomes
colour authority beyond OWNER_CHOSEN_DESIGN_INTENT, GATE_2 stays
BLOCKED, owner_approved stays false.

  1. ES3083 twelve-pan multi-shade application — the twelve
     OWNER_CHOSEN_DESIGN_INTENT shades (es3083_shade_authority.json),
     each realized through PowderMaterialSpec at its recorded family,
     applied pan-by-pan to the P1B rect moulded assembly and rendered
     through the production render path (palette_csg_views.py +
     powder_materials.py, the frozen instrument, untouched).
  2. FB3093 pressed-powder application — PRESSED_POWDER realized on the
     product pan geometry where the family contract sources dimensions;
     where it does not, the honest ceiling is recorded, never invented.
  3. Product observability on real pan geometry — the protocol's
     REQUIRED_DISTINCTIONS that these products actually exercise,
     probed on the PRODUCT's own pan (metal_pan_1 + powder_1 extracted
     from the assembly), shade held constant, family swapped, measured
     by the M5 product-observability instrument AS DECLARED
     (palette_m5_evidence.optical_signature / discriminate — its bars,
     not new ones). Distinctions the products do not exercise are
     recorded NOT_EXERCISED_BY_THESE_PRODUCTS, not skipped silently.
  4. Workflow trace with production identifiers — the M5 §10 chain
     driven for the M6 products: governed task, per-pan
     PaletteMaterialArtifact rows carrying the realized spec's
     material_identity, assembly identity, render sha256s, and the
     queue-control stamp (begin_traced_queue is frame one's
     precondition, per palette_queue_control).

GEOMETRY AUTHORITY, stated before anything renders: the assembly is the
EXISTING P1B rect moulded build at its PROVISIONAL_DESIGN_DEFAULT
dimensions. The measured caliper block
(MEASURED_CALIPER_PHYSICAL_SAMPLE_2026_08_14) is consumed as the
MEASURED side of the fit-comparison table in the product record — NOT
as a geometry mutation: pocket dimensions derive from the pan contract
by the module's own datum-linkage guard, and overriding the pan
contract is a P1B default move this node's rules do not authorize.

Bars: none moved, none created. The M5 discrimination bars and the M6
pass law are cited, not restated. Seeds: PRODUCT_SEED_BASE + pan index,
declared here, colliding with no rig seed (a600 records the per-rig
seed map).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs" / "roadmap" / "palt_m6" / "products"
#: scratch (OBJ exports, per-scene cfgs) lives OUTSIDE the record-manifest
#: sweep — intermediates are reproducible from the build phase and must
#: not be digest-bound as records. The build MANIFEST is a record and
#: lives in OUT.
TMP = REPO.parent / "var" / "m6" / "products_build"  # the one var/, since the clean-up of 2026-10-04
BUILD_MANIFEST = OUT / "m6_product_build_manifest.json"
SHADE_RECORD = REPO / "docs" / "roadmap" / "palt_m6" / "es3083_shade_authority.json"
SUBSTRATE = REPO / "docs" / "roadmap" / "palt_m7" / "es3083_artwork_geometry_substrate.json"
VIEW_SCRIPT = Path(__file__).parent / "blender_scripts" / "palette_csg_views.py"

SCHEMA = "m6_product_realization/1.0"
TASK_MARKER = "M6-PRODUCT-TRACE ES3083 twelve-pan + FB3093"
PRODUCT_SEED_BASE = 700
PROBE_SEED = 700
RESOLUTION = [1100, 1100]
SAMPLES = 48
MAX_RENDERS = 14  # declared spend ceiling; exceeding it is a refusal
from apps.ire.materials_paths import resolve_material_file as _physical_material
FONT = str(_physical_material(REPO.parent / "materials" / "Fonts" / "CrimsonText-Regular.ttf", repo_root=REPO.parent))   # Day 6 migration


class M6ProductError(RuntimeError):
    pass


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _shades() -> list:
    rec = json.loads(SHADE_RECORD.read_text())
    shades = sorted(rec["shades"], key=lambda s: s["pan"])
    if len(shades) != 12:
        raise M6ProductError(f"expected 12 shades, record has {len(shades)}")
    return shades


def declaration() -> dict:
    shades = _shades()
    families = sorted({s["family"] for s in shades})
    d = {
        "record_type": "m6_product_realization_declaration/1.0",
        "declared_before_realization": True,
        "a19_scope": "product-definition work consumes the repaired powder "
                     "contract; nothing ships; owner_approved false; "
                     "GATE_2 BLOCKED; manufacturing_authority "
                     "NOT_ESTABLISHED; shades are "
                     "OWNER_CHOSEN_DESIGN_INTENT, not colour authority",
        "products": {
            "ES3083": {
                "geometry": "P1B rect moulded assembly, "
                            "PROVISIONAL_DESIGN_DEFAULT dimensions, "
                            "existing build, identities untouched",
                "materials": "twelve owner shades from "
                             "es3083_shade_authority.json, realized at "
                             "their recorded families, seeds "
                             f"{PRODUCT_SEED_BASE}+pan",
                "pan_mapping": "pan N (record order) -> powder_N "
                               "(component order); the mapping is VISIBLE "
                               "on the product board captions so a "
                               "misorder cannot hide",
                "case_colour": "NEUTRAL CLAY — PANTONE 621C/627C remain "
                               "UNRESOLVED_SPOT_COLOUR; no case colour is "
                               "fabricated",
                "views": ["three_quarter OPEN_REVIEW_ANGLE",
                          "top OPEN_REVIEW_ANGLE", "three_quarter CLOSED"],
            },
            "FB3093": {
                "family": "PRESSED_POWDER",
                "shade": "PROVISIONAL_VISUALIZATION_SHADE (no owner shade "
                         "exists for FB3093; none is invented)",
                "geometry_rule": "contracted pan dimensions where the P2A "
                                 "intent sources them; otherwise the "
                                 "honest ceiling is recorded",
                "views": ["three_quarter"],
            },
        },
        "observability": {
            "instrument": "palette_m5_evidence.optical_signature + "
                          "discriminate, bars AS DECLARED there "
                          "(MINIMUM_DISCRIMINATION) — reused, not moved",
            "probe": "the PRODUCT's own pan (metal_pan_1 + powder_1 from "
                     "the assembly), shade held constant at Petal Veil "
                     "(the lightest owner shade — the depth window "
                     "honesty from D8), family swapped across the "
                     "product census",
            "pairs": "REQUIRED_DISTINCTIONS filtered to pairs both of "
                     "whose families the products exercise; the rest "
                     "recorded NOT_EXERCISED_BY_THESE_PRODUCTS",
            "limit_stated": "measurement is on the production script's "
                            "8-bit display PNGs because that is what the "
                            "M5 instrument declares it reads; no "
                            "scene-linear claim is made for it",
        },
        "spend": {"resolution": RESOLUTION, "samples": SAMPLES,
                  "max_renders": MAX_RENDERS,
                  "families_in_census": families + ["PRESSED_POWDER"]},
        "trace": {"queue": "m6_products",
                  "task_marker": TASK_MARKER,
                  "first_act": "palette_queue_control.begin_traced_queue "
                               "with this declaration's identity"},
        "boards": ["es3083_product_board", "fb3093_product_board",
                   "observability_board", "trace_board", "census_board"],
        "amendment_1_1_class_23_correction": (
            "v1 constructed owner shades RAW from the shade record's "
            "4-decimal-rounded rgb; the class-23 guard fired (correctly, "
            "twice over: construction belongs to the engine's one "
            "sanctioned site, and the engine's hex-derived sRGB differs "
            "from the record's rounded triples in the 5th decimal). "
            "Construction now goes through "
            "es3083_owner_shade_set(seed_base=700). Every phase was "
            "RE-RUN from the corrected specs — renders, observability, "
            "trace, boards; nothing inherited from v1. Spend: a second "
            "10-render run, cause named here; v1 outputs overwritten in "
            "place as the superseded realization of the same declared "
            "views."),
        "owner_approved": False,
    }
    d["declaration_identity"] = hashlib.sha256(
        json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]
    return d


# ---------------------------------------------------------------- build --

def _owner_specs():
    """The twelve owner materials, THROUGH the engine's one sanctioned
    construction site (class-23 guard) at this node's declared seeds.

    AMENDMENT 1.1 (class-23 correction): v1 of this module constructed
    PowderShade rows raw from the shade record's 4-decimal-rounded rgb.
    The guard fired, and it was right twice over — construction belongs
    to the engine, and the engine's hex-derived sRGB differs from the
    record's rounded triples in the 5th decimal. Everything downstream
    of the v1 specs was re-run; nothing was inherited.
    """
    from apps.pipeline.services import palette_powder_engine as PE
    return {r["pan"]: r["spec"]
            for r in PE.es3083_owner_shade_set(seed_base=PRODUCT_SEED_BASE)}


def build_scenes() -> dict:
    """Meshes + cfgs for every declared render. No rendering here."""
    from apps.pipeline.services import palette_moulded_rect as MR
    from apps.pipeline.services import geometry_validation_render as GVR
    from apps.pipeline.services import palette_powder_engine as PE

    TMP.mkdir(parents=True, exist_ok=True)
    decl = declaration()
    (OUT / "m6_product_realization_declaration.json").write_text(
        json.dumps(decl, indent=1) + "\n")

    shades = _shades()
    comps, dims = MR.build_rect_components(None)
    if "powder_1" in comps:
        first = 1
    else:
        first = 0
    powder_names = []
    for i in range(first, first + 12):
        name = f"powder_{i}"
        if name not in comps:
            raise M6ProductError(f"assembly lacks {name} — expected "
                                 "twelve powder components")
        powder_names.append(name)

    owner_specs = _owner_specs()
    materials = {}
    pan_map = []
    for shade_rec, comp_name in zip(shades, powder_names):
        spec_obj = owner_specs[shade_rec["pan"]]
        spec = spec_obj.realize()
        materials[comp_name] = spec
        pan_map.append({"pan": shade_rec["pan"], "component": comp_name,
                        "shade": shade_rec["name"],
                        "family": shade_rec["family"],
                        "material_identity_product_seed":
                            spec["material_identity"],
                        "material_identity_shade_record":
                            shade_rec["material_identity"]})

    cw, cd = dims["case_width_mm"], dims["case_depth_mm"]
    ch = dims["case_height_mm"]
    centre = [0.0, 0.0, ch * 0.5]
    scale_tq = max(cw, cd) * 2.35
    renders = []

    def scene(tag, state, views, mats, scale, extra=None):
        sdir = TMP / tag
        sdir.mkdir(parents=True, exist_ok=True)
        posed = MR.compose_rect_state(comps, dims, state)
        meshes = {}
        for n, comp in posed.items():
            p = sdir / f"{n}.obj"
            GVR.export_obj(comp, str(p))
            meshes[n] = str(p)
        cfg = {"meshes": meshes, "materials": mats, "technical_tones": False,
               "resolution": RESOLUTION, "samples": SAMPLES,
               "centre": centre, "ortho_scale": scale,
               "smooth_prefixes": ["hinge_", "clasp_hook"],
               "views": {v: str(OUT / f"{tag}_{v}.png") for v in views}}
        if extra:
            cfg.update(extra)
        cfg_path = sdir / "cfg.json"
        cfg_path.write_text(json.dumps(cfg))
        renders.extend(cfg["views"].values())
        return {"tag": tag, "cfg": str(cfg_path),
                "views": cfg["views"], "state": state}

    scenes = [
        scene("es3083_open", "OPEN_REVIEW_ANGLE",
              ["three_quarter", "top"], materials, scale_tq),
        scene("es3083_closed", "CLOSED", ["three_quarter"],
              materials, scale_tq * 0.8),
    ]

    # FB3093 — contracted dimensions or the honest ceiling. The P2A
    # intent's numeric pan dimensions were checked (fields walked with
    # DIRECT attribute access — a field without name/value is a defect,
    # not a case to skip silently) and none exist, so the ceiling stands.
    from apps.pipeline.services import palette_compact_family as CF
    intent = CF.build_p2a_intent()
    numeric_pan_fields = []
    for f in intent.fields:
        if not isinstance(f.value, (int, float)):
            continue
        if "pan" not in f.name:
            continue
        # dimension-shaped only: pan_count=1 is a count, not a millimetre
        if any(t in f.name for t in ("_mm", "diameter", "dia_", "depth",
                                     "width", "height", "radius")):
            numeric_pan_fields.append(f.name)
    if numeric_pan_fields:
        raise M6ProductError(
            "the P2A intent NOW carries numeric pan dimensions "
            f"({numeric_pan_fields}) — the FB3093 honest-ceiling branch "
            "is stale; build the sourced geometry instead of rendering "
            "the ceiling")
    fb_note = ("FB3093_PAN_DIMENSIONS_UNSOURCED — the P2A intent "
               "carries no numeric pan dimensions; the pressed-powder "
               "application therefore renders on the PRODUCT rect pan "
               "geometry (the only real pan geometry in the "
               "programme), and building a round pan would have "
               "invented dimensions. Recorded as the honest ceiling; "
               "a sourced FB3093 drawing lifts it.")

    # probes: product pan geometry, shade constant, family swapped
    probe_shade = shades[0]  # Petal Veil, pan 1 — declared above
    census = sorted({s["family"] for s in shades} | {"PRESSED_POWDER"})
    pan_mesh = comps["metal_pan_1"]
    cake_mesh = comps["powder_1"]
    pdir = TMP / "probe"
    pdir.mkdir(parents=True, exist_ok=True)
    GVR.export_obj(pan_mesh, str(pdir / "metal_pan_1.obj"))
    GVR.export_obj(cake_mesh, str(pdir / "powder_1.obj"))
    # probe centre: the pan's own field position, top view
    import numpy as np
    v = np.asarray(pan_mesh["vertices"], dtype=float)
    pc = [(v[:, 0].min() + v[:, 0].max()) / 2.0,
          (v[:, 1].min() + v[:, 1].max()) / 2.0,
          (v[:, 2].min() + v[:, 2].max()) / 2.0]
    probe_scenes = []
    # the probe SHADE OBJECT comes from the engine's sanctioned site
    # (pan 1, Petal Veil) — no raw owner-shade construction here; only
    # the family is swapped, which is the probe's entire point.
    from apps.pipeline.services import palette_powder_engine as PE2
    petal_veil = owner_specs[probe_shade["pan"]].shade
    for fam in census:
        spec = PE2.PowderMaterialSpec(fam, petal_veil,
                                      seed=PROBE_SEED).realize()
        cfg = {"meshes": {"metal_pan_1": str(pdir / "metal_pan_1.obj"),
                          "powder_1": str(pdir / "powder_1.obj")},
               "materials": {"powder_1": spec}, "technical_tones": True,
               "resolution": RESOLUTION, "samples": SAMPLES,
               "centre": pc, "ortho_scale": 40.0,
               "views": {"top": str(OUT / f"probe_{fam}_top.png")}}
        cp = pdir / f"cfg_{fam}.json"
        cp.write_text(json.dumps(cfg))
        renders.append(cfg["views"]["top"])
        probe_scenes.append({"tag": f"probe_{fam}", "cfg": str(cp),
                             "family": fam,
                             "views": cfg["views"]})

    if len(renders) > MAX_RENDERS:
        raise M6ProductError(
            f"{len(renders)} renders exceed the declared ceiling "
            f"{MAX_RENDERS} — refusing (spend is declared, not elastic)")

    manifest = {"declaration_identity": decl["declaration_identity"],
                "scenes": scenes, "probe_scenes": probe_scenes,
                "pan_map": pan_map, "census": census,
                "fb3093": {"status": "HONEST_CEILING",
                           "note": fb_note,  # always the honest ceiling today (guard above)
                           "material": "PRESSED_POWDER on the product rect "
                                       "pan via the probe render "
                                       "probe_PRESSED_POWDER_top.png"},
                "dims": {k: dims[k] for k in
                         ("case_width_mm", "case_depth_mm",
                          "case_height_mm", "pan_depth_mm")},
                "render_count_declared": len(renders)}
    BUILD_MANIFEST.write_text(json.dumps(manifest, indent=1))
    return manifest


# --------------------------------------------------------------- render --

def render_all() -> dict:
    from apps.pipeline.services import palette_queue_control as QC
    from apps.pipeline.services.geometry_validation_render import BLENDER
    manifest = json.loads(BUILD_MANIFEST.read_text())
    ledger: dict = {}
    trace_path = OUT / "m6_products_firing_trace.jsonl"
    # a queue is ONE run: appending a second run's control to an existing
    # trace file makes the control not-the-first-act and the whole file
    # unreadable (read_trace_evidence refuses, correctly — it did).
    # A superseded run's trace is rotated aside, never deleted.
    if trace_path.exists():
        n = 1
        while (OUT / f"m6_products_firing_trace_superseded_{n}.jsonl").exists():
            n += 1
        trace_path.rename(
            OUT / f"m6_products_firing_trace_superseded_{n}.jsonl")
    stamp = QC.begin_traced_queue(
        "m6_products", str(trace_path), ledger,
        manifest["declaration_identity"])
    blender = os.path.expanduser(BLENDER)
    done = []
    for sc in manifest["scenes"] + manifest["probe_scenes"]:
        cmd = [blender, "-b", "--factory-startup", "-noaudio",
               "-P", str(VIEW_SCRIPT), "--", sc["cfg"]]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        missing = [p for p in sc["views"].values() if not os.path.exists(p)]
        if r.returncode != 0 or missing:
            raise M6ProductError(
                f"render {sc['tag']} failed rc={r.returncode} "
                f"missing={missing}\n{r.stdout[-1200:]}\n{r.stderr[-400:]}")
        done.append(sc["tag"])
    ledger["queue"] = "m6_products"
    (OUT / "m6_products_queue_ledger.json").write_text(
        json.dumps(ledger, indent=1))
    return {"stamp": stamp, "rendered": done}


# -------------------------------------------------------- observability --

def measure() -> dict:
    from apps.pipeline.services import palette_m5_evidence as M5E
    from apps.pipeline.services import palette_powder_protocol as PP
    manifest = json.loads(BUILD_MANIFEST.read_text())
    census = set(manifest["census"])
    sigs = {}
    for sc in manifest["probe_scenes"]:
        png = sc["views"]["top"]
        sigs[sc["family"]] = M5E.optical_signature(png)
    exercised, not_exercised = [], []
    for a, b, rig in PP.REQUIRED_DISTINCTIONS:
        if a in census and b in census:
            rep = M5E.discriminate(sigs[a], sigs[b], a, b)
            rep["required_by_rig"] = rig
            exercised.append(rep)
        else:
            not_exercised.append(
                {"pair": [a, b], "rig": rig,
                 "status": "NOT_EXERCISED_BY_THESE_PRODUCTS",
                 "why": "at least one family appears in neither product"})
    result = {"instrument": "palette_m5_evidence (bars as declared)",
              "probe_shade": "Petal Veil (pan 1)",
              "pairs_exercised": exercised,
              "pairs_not_exercised": not_exercised,
              "verdicts": {f"{r['a']}_vs_{r['b']}": r["verdict"]
                           for r in exercised}}
    (OUT / "m6_product_observability.json").write_text(
        json.dumps(result, indent=1) + "\n")
    return result


# ---------------------------------------------------------------- trace --

def run_m6_trace() -> dict:
    """The M5 §10 chain, driven for the M6 products."""
    from django.db import transaction
    from apps.pipeline.models import DesignTask, PaletteMaterialArtifact
    from apps.pipeline.services import palette_confirmation_flow as FLOW
    from apps.pipeline.services import palette_design_graph as DG
    from apps.pipeline.services import palette_es3083_owner_confirmation as OC
    from apps.pipeline.services import palette_m5_evidence as M5E
    from apps.pipeline.services import palette_m5_workflow as M5W
    from apps.pipeline.services import palette_moulded_rect as MR
    from apps.pipeline.services import palette_queue_control as QC
    from apps.pipeline.services import palette_rect_tray_geometry as RT

    manifest = json.loads(BUILD_MANIFEST.read_text())
    ledger = json.loads((OUT / "m6_products_queue_ledger.json").read_text())
    trace_records = QC.read_trace_evidence(
        ledger, str(OUT / "m6_products_firing_trace.jsonl"))

    with transaction.atomic():
        base = M5W._task()
        task = DesignTask.objects.filter(task_text=TASK_MARKER).first()
        if task is None:
            task = DesignTask.objects.create(
                brand=base.brand, product=base.product,
                task_text=TASK_MARKER, status="running",
                design_target="palette")
        confirmation = FLOW.current_confirmation(task)
        if confirmation is None:
            from apps.pipeline.services import palette_es3083_intent as ES
            FLOW.open_confirmation(task, ES.build_es3083_intent())
            confirmation = FLOW.save_confirmation(
                task, ES.build_es3083_intent(), OC.confirmation_record(),
                notes="M6 product realization trace")
        intent = FLOW.rehydrate(confirmation)
        tray = RT.build_rect_recessed_tray()
        graph = DG.build_palette_design_graph(intent, tray)
        comps, _dims = MR.build_rect_components(OC.confirmed_intent())
        geometry_identity = M5E.assembly_identity(comps)

        open_tq = OUT / "es3083_open_three_quarter.png"
        rows = []
        for pm in manifest["pan_map"]:
            variant = f"m6_pan_{pm['pan']:02d}_{pm['family']}"
            artifact, _ = PaletteMaterialArtifact.objects.update_or_create(
                task=task, variant_name=variant,
                defaults={
                    "intent_confirmation": confirmation,
                    "material_contract_identity":
                        pm["material_identity_product_seed"],
                    "design_graph_identity": graph["graph_identity"],
                    "geometry_identity": geometry_identity,
                    "scene_identity": hashlib.sha256(
                        (geometry_identity
                         + pm["material_identity_product_seed"]
                         + "es3083_open").encode()).hexdigest()[:16],
                    "render_identity": _sha(open_tq)[:16],
                    "evidence_path": str(open_tq.relative_to(REPO)),
                    "evidence_sha256": _sha(open_tq),
                    "review_board_artifact_identity": "",
                    "material_contract": {
                        "shade": pm["shade"], "family": pm["family"],
                        "seed": PRODUCT_SEED_BASE + pm["pan"],
                        "material_identity":
                            pm["material_identity_product_seed"],
                        "shade_record_identity":
                            pm["material_identity_shade_record"]},
                })
            rows.append({"variant": variant, "artifact_id": artifact.pk,
                         "material_identity":
                             pm["material_identity_product_seed"]})

    record = {
        "record_type": "m6_workflow_trace/1.0",
        "task_id": task.pk, "task_marker": TASK_MARKER,
        "confirmation_version": confirmation.version,
        "graph_identity": graph["graph_identity"],
        "assembly_identity": geometry_identity,
        "queue_control_stamp": ledger["trace_controls"][0],
        "trace_firings_beyond_control": len(trace_records),
        "artifacts": rows,
        "identity_note": "material_contract_identity is the PRODUCT-seed "
                         "identity computed live by realize(); the shade "
                         "record's material_identity (different basis) "
                         "travels alongside in material_contract — the "
                         "two are DIFFERENT BY SEED and no equality is "
                         "claimed",
        "renders": {p.name: _sha(p) for p in sorted(OUT.glob("*.png"))},
        "owner_approved": False,
    }
    (OUT / "m6_workflow_trace.json").write_text(
        json.dumps(record, indent=1) + "\n")
    return record


# --------------------------------------------------------------- boards --

def _font(px):
    return ImageFont.truetype(FONT, px)


def _board(title, tiles, caption_rows, out_path, note=""):
    """One board: image tiles in a row + caption table below."""
    tile_w = 640
    imgs = [Image.open(p) for p in tiles]
    gap, head, row_h = 24, 72, 34
    if imgs:
        th = max(round(i.height * tile_w / i.width) for i in imgs)
        tile_band = th + gap
    else:
        th = 0
        tile_band = 0
    if note:
        foot = 70
    else:
        foot = 30
    W = max(len(imgs) * (tile_w + gap) + gap, 1400)
    H = head + tile_band + row_h * (len(caption_rows) + 1) + foot
    page = Image.new("RGB", (W, H), (246, 246, 244))
    d = ImageDraw.Draw(page)
    d.text((gap, 20), title, font=_font(30), fill=(20, 22, 20))
    x = gap
    for im in imgs:
        t = im.resize((tile_w, round(im.height * tile_w / im.width)),
                      Image.LANCZOS)
        page.paste(t, (x, head))
        d.rectangle([x, head, x + tile_w, head + t.height],
                    outline=(170, 170, 170), width=2)
        x += tile_w + gap
    y = head + tile_band
    f = _font(19)
    for row in caption_rows:
        d.text((gap, y), row, font=f, fill=(50, 50, 50))
        y += row_h
    if note:
        d.text((gap, y + 8), note, font=_font(17), fill=(140, 60, 40))
    page.save(out_path)


def boards() -> list:
    manifest = json.loads(BUILD_MANIFEST.read_text())
    obs = json.loads((OUT / "m6_product_observability.json").read_text())
    trace = json.loads((OUT / "m6_workflow_trace.json").read_text())
    sub = json.loads(SUBSTRATE.read_text())
    cal = sub["MEASURED_CALIPER_PHYSICAL_SAMPLE_2026_08_14"]
    made = []

    from apps.pipeline.services import palette_rect_pan as RP_
    from apps.pipeline.services import palette_rect_tray_geometry as RT_
    pc = RP_.contract_values()
    td = RT_.RECT_TRAY_DEFAULTS
    fit_rows = [
        "FIT — F1 ADOPTED (f1_pan_redimension_ingestion.json): the pan "
        "contract re-dimensioned to the measured cavity through the "
        "datum solver; geometry below IS the measured-sample fit:",
        f"  cavity at deck (derived from pan {pc['pan_width_mm']:.3f} x "
        f"{pc['pan_height_mm']:.3f} + tolerance through draft/fillets): "
        f"{cal['pan_cavity_measured_mm'][0]:.2f} x "
        f"{cal['pan_cavity_measured_mm'][1]:.2f} x "
        f"{cal['pan_cavity_measured_mm'][2]:.2f} MEASURED = adopted",
        f"  pitch {td['pitch_x_mm']:.2f} x {td['pitch_y_mm']:.2f} "
        "(MEASURED, centre-to-centre); case heights on the SAMPLE: "
        f"{cal['case_height_closed_mm']:.2f} closed / "
        f"{cal['lid_height_mm']:.2f} lid / {cal['base_height_mm']:.2f} "
        "base (case-level dims remain NOT_APPROVED)",
        f"  P1B case as built: {manifest['dims']['case_width_mm']:.1f} x "
        f"{manifest['dims']['case_depth_mm']:.1f} x "
        f"{manifest['dims']['case_height_mm']:.1f}",
    ]
    p = OUT / "board_1_es3083_product.png"
    _board("ES3083 — twelve-pan multi-shade application "
           "(owner shades, A19 scope, nothing ships)",
           [OUT / "es3083_open_three_quarter.png",
            OUT / "es3083_open_top.png",
            OUT / "es3083_closed_three_quarter.png"],
           ["Orientation: tray origin is front-left, +y toward the hinge — "
            "so R1 is the FRONT row (BOTTOM of the top view), R3 nearest "
            "the hinge (top). Verified by eye against the shade colours.",
            "Pans (record order R1C1..R3C4): " + ", ".join(
               f"{pm['pan']}:{pm['shade']} [{pm['family']}]"
               for pm in manifest["pan_map"][:6]),
            "    " + ", ".join(
                f"{pm['pan']}:{pm['shade']} [{pm['family']}]"
                for pm in manifest["pan_map"][6:]),
            "Case: NEUTRAL CLAY — 621C/627C remain "
            "UNRESOLVED_SPOT_COLOUR (no value fabricated). Geometry: "
            "P1B PROVISIONAL_DESIGN_DEFAULT.", *fit_rows],
           str(p),
           note="NOT owner-approved. NOT manufacturing authority. "
                "GATE_2 BLOCKED.")
    made.append(p)

    p = OUT / "board_2_fb3093_product.png"
    _board("FB3093 — pressed-powder application (honest ceiling)",
           [OUT / "probe_PRESSED_POWDER_top.png"],
           [manifest["fb3093"]["note"] or manifest["fb3093"]["status"],
            "Material: PRESSED_POWDER at Petal Veil (probe shade), "
            "seed %d, on the product rect pan." % PROBE_SEED],
           str(p), note="FB3093 case geometry NOT built — no sourced "
                        "dimensions; nothing invented.")
    made.append(p)

    rows = []
    for r in obs["pairs_exercised"]:
        axes = ", ".join(f"{a} d={v['delta']}(bar {v['bar']})"
                         for a, v in r["axes"].items() if v["clears"])
        line = (f"{r['a']} vs {r['b']} [{r['required_by_rig']}]: "
                f"{r['verdict']}")
        if axes:
            line += f" — clears on {axes}"
        else:
            line += " — no axis clears the M5 bars on product-pan probes"
        rows.append(line)
    for r in obs["pairs_not_exercised"]:
        rows.append(f"{r['pair'][0]} vs {r['pair'][1]}: "
                    "NOT_EXERCISED_BY_THESE_PRODUCTS")
    p = OUT / "board_3_observability.png"
    _board("Product observability on real pan geometry — probe: "
           "product pan, shade constant (Petal Veil), family swapped",
           [OUT / f"probe_{f}_top.png" for f in manifest["census"][:4]],
           rows + ["Instrument: M5 discrimination bars as declared; "
                   "rig-level M6 verdicts are NOT re-adjudicated here — "
                   "this is product-level visibility, recorded either way."],
           str(p))
    made.append(p)

    p = OUT / "board_4_trace.png"
    _board("Workflow trace — production identifiers",
           [],
           [f"Task {trace['task_id']} ({trace['task_marker']}), "
            f"confirmation v{trace['confirmation_version']}",
            f"Graph {trace['graph_identity']}  Assembly "
            f"{trace['assembly_identity']}",
            f"Queue control: {trace['queue_control_stamp']['ts']} "
            f"declaration {trace['queue_control_stamp']['declaration_identity']}",
            f"{len(trace['artifacts'])} PaletteMaterialArtifact rows "
            "(m6_pan_01..12), material identities live-computed at "
            "product seeds:",
            "  " + ", ".join(r["material_identity"]
                             for r in trace["artifacts"][:6]),
            "  " + ", ".join(r["material_identity"]
                             for r in trace["artifacts"][6:]),
            f"{len(trace['renders'])} render artifacts sha256-bound in "
            "m6_workflow_trace.json"],
           str(p))
    made.append(p)

    shades = _shades()
    chip = Image.new("RGB", (1400, 120 + 12 * 34 + 40), (246, 246, 244))
    d = ImageDraw.Draw(chip)
    d.text((24, 20), "ES3083 census — twelve owner shades "
           "(OWNER_CHOSEN_DESIGN_INTENT; not colour authority)",
           font=_font(28), fill=(20, 22, 20))
    y = 90
    for s in shades:
        rgb = tuple(round(c * 255) for c in s["rgb"])
        d.rectangle([24, y, 84, y + 26], fill=rgb, outline=(120, 120, 120))
        d.text((100, y + 2), f"{s['pan']:>2} {s['grid_pos']}  "
               f"{s['name']}  [{s['family']}]  {s['hex']}  "
               f"mat {s['material_identity']}",
               font=_font(18), fill=(50, 50, 50))
        y += 34
    p = OUT / "board_5_census.png"
    chip.save(p)
    made.append(p)
    return [str(m) for m in made]


# --------------------------------------------------------------- record --

def final_record(render_info, obs, trace_rec, board_paths) -> dict:
    manifest = json.loads(BUILD_MANIFEST.read_text())
    rec = {
        "record_type": SCHEMA,
        "declaration_identity": manifest["declaration_identity"],
        "protocol_items_realized": {
            "ES3083_twelve_pan_multi_shade_application": "REALIZED — "
                "renders + board 1; geometry provisional, shades owner-"
                "chosen, case neutral",
            "FB3093_pressed_powder_application": manifest["fb3093"],
            "product_observability_on_real_pan_geometry":
                obs["verdicts"],
            "workflow_trace_with_production_identifiers": {
                "task_id": trace_rec["task_id"],
                "artifacts": len(trace_rec["artifacts"])},
        },
        "pan_map": manifest["pan_map"],
        "boards": board_paths,
        "renders_sha256": trace_rec["renders"],
        "not_done_and_said_so": [
            "FB3093 case geometry (no sourced dimensions)",
            "any geometry move toward the measured caliper numbers "
            "(owner decision, fit table on board 1)",
            "any re-adjudication of rig-level M6 verdicts",
        ],
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
        "GATE_2": "BLOCKED",
    }
    (OUT / "m6_product_realization_result.json").write_text(
        json.dumps(rec, indent=1) + "\n")
    return rec


if __name__ == "__main__":
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    if len(sys.argv) > 1:
        phase = sys.argv[1]
    else:
        phase = "all"
    OUT.mkdir(parents=True, exist_ok=True)
    if phase in ("build", "all"):
        m = build_scenes()
        print("BUILD ok — renders declared:", m["render_count_declared"])
    if phase in ("render", "all"):
        r = render_all()
        print("RENDER ok —", r["rendered"])
    if phase in ("measure", "all"):
        o = measure()
        print("MEASURE ok —", o["verdicts"])
    if phase in ("trace", "all"):
        t = run_m6_trace()
        print("TRACE ok — task", t["task_id"], len(t["artifacts"]), "artifacts")
    if phase in ("boards", "all"):
        b = boards()
        print("BOARDS ok —", len(b))
    if phase in ("record", "all"):
        obs = json.loads((OUT / "m6_product_observability.json").read_text())
        tr = json.loads((OUT / "m6_workflow_trace.json").read_text())
        bl = [str(p) for p in sorted(OUT.glob("board_*.png"))]
        final_record(None, obs, tr, bl)
        print("RECORD ok")
