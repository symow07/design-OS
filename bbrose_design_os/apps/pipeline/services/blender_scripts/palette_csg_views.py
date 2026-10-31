"""PALT-M4B — CSG-resolved neutral views and TRUE sections.

Components may declare a CSG difference (tray blank minus drafted pocket
cutters, knuckle minus bore, base minus cavity and finger notch). Those
Booleans are solved here, so recessed pockets are real geometry.

Sections are cut with a Boolean against a half-space box — a genuine
cutaway, never a clipped exterior view.

Neutral MEDIUM-GREY clay + studio lighting with contact shading, so
mechanism detail is visible at review resolution. No beauty colour.

Run: Blender -b --factory-startup -noaudio -P palette_csg_views.py -- cfg.json
"""
import json
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import powder_materials  # noqa: E402 — M6 structural powder graphs

cfg = json.load(open(sys.argv[sys.argv.index("--") + 1]))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = cfg.get("samples", 48)
scene.cycles.seed = 0
scene.cycles.use_denoising = False
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "8"
scene.render.film_transparent = False

objs = {}
for name, path in cfg["meshes"].items():
    # deselect first: without this, selected_objects[0] can return a
    # PREVIOUSLY imported object and every subsequent name is attached to
    # the wrong mesh — which silently breaks the CSG targets
    bpy.ops.object.select_all(action="DESELECT")
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path, forward_axis='Y', up_axis='Z')
    new = [o for o in bpy.data.objects if o not in before]
    if len(new) != 1:
        raise RuntimeError(f"import of {name} produced {len(new)} objects")
    obj = new[0]
    obj.name = name
    # the EXACT Boolean solver needs freshly evaluated mesh data; without
    # this the modifier silently produces no cut
    obj.data.update()
    obj.data.calc_loop_triangles()
    objs[name] = obj

# --- resolve declared CSG differences -------------------------------------
consumed = set()
for target, spec in cfg.get("csg", {}).items():
    if target not in objs:
        continue
    for cutter in spec.get("cutters", []):
        if cutter not in objs:
            continue
        mod = objs[target].modifiers.new(f"bool_{cutter}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = objs[cutter]
        mod.solver = "EXACT"
        consumed.add(cutter)
    # modifiers are NOT applied: Cycles evaluates the stack at render
    # time, which avoids the ops/selection-context pitfalls entirely

# refresh mesh data AFTER the modifiers exist — the EXACT solver reads
# the cutter's evaluated mesh, and refreshing beforehand is not enough
for obj in objs.values():
    obj.data.update()
    obj.data.calc_loop_triangles()
bpy.context.view_layer.update()

for cutter in consumed:
    objs[cutter].hide_render = True

# --- true section: Boolean against a half-space box ------------------------
section = cfg.get("section")
if section:
    axis = section.get("axis", "y")
    at = float(section.get("at", 0.0))
    size = float(section.get("size", 400.0))
    bpy.ops.mesh.primitive_cube_add(size=size)
    cutbox = bpy.context.active_object
    cutbox.name = "SECTION_CUTTER"
    off = size / 2.0
    if axis == "y":
        cutbox.location = (0.0, at + off, 0.0)
    elif axis == "x":
        cutbox.location = (at + off, 0.0, 0.0)
    else:
        cutbox.location = (0.0, 0.0, at + off)
    for name, obj in objs.items():
        if obj.hide_render or name == "SECTION_CUTTER":
            continue
        mod = obj.modifiers.new("section", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = cutbox
        mod.solver = "EXACT"
    cutbox.hide_render = True

# --- materials: neutral medium grey + optional technical differentiation ---
def clay(name, rgb, rough=0.62):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgb + (1.0,)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = 0.32
    return mat


NEUTRAL = clay("NEUTRAL_MEDIUM_GREY_CLAY", (0.42, 0.42, 0.425))
TONES = {
    "pan": clay("TECH_PAN", (0.55, 0.56, 0.58), 0.35),
    "powder": clay("TECH_POWDER", (0.30, 0.30, 0.31), 0.95),
    "mirror": clay("TECH_MIRROR", (0.62, 0.63, 0.66), 0.12),
    "adhesive": clay("TECH_ADHESIVE", (0.34, 0.32, 0.30), 0.85),
    "hinge": clay("TECH_HINGE", (0.50, 0.50, 0.52), 0.30),
    "clasp": clay("TECH_CLASP", (0.50, 0.50, 0.52), 0.30),
    "rib": clay("TECH_RIB", (0.38, 0.38, 0.39), 0.70),
}
def from_contract(name, spec):
    """A material resolved by palette_material_engine.

    M5 drives the real production render path, so a resolved material
    contract lands here rather than in a demonstration renderer that
    bypasses the workflow.
    """
    mat = bpy.data.materials.new(f"M5_{name}")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    rgb = spec.get("display_rgb") or [0.5, 0.5, 0.5]
    b.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    b.inputs["Roughness"].default_value = spec.get("roughness", 0.55)
    b.inputs["Metallic"].default_value = spec.get("metallic", 0.0)
    trans = spec.get("transmission", 0.0)
    if trans:
        b.inputs["Transmission Weight"].default_value = trans
        b.inputs["IOR"].default_value = spec.get("ior", 1.49)
        mat.use_screen_refraction = True
    if spec.get("sheen"):
        b.inputs["Sheen Weight"].default_value = spec["sheen"]
    if spec.get("clearcoat"):
        b.inputs["Coat Weight"].default_value = spec["clearcoat"]
    b.inputs["Specular IOR Level"].default_value = 0.5 if trans else 0.32
    return mat


MATERIALS = cfg.get("materials") or {}
technical = cfg.get("technical_tones", False)
for name, obj in objs.items():
    obj.data.materials.clear()
    mat = NEUTRAL
    if name in MATERIALS:
        spec = MATERIALS[name]
        mat = (powder_materials.build(name, spec)
               if spec.get("powder_family")
               else from_contract(name, spec))
    elif technical:
        if name.startswith("metal_pan_"):
            mat = TONES["pan"]
        elif name.startswith("powder_"):
            mat = TONES["powder"]
        elif name == "mirror":
            mat = TONES["mirror"]
        elif name.startswith("mirror_adhesive"):
            mat = TONES["adhesive"]
        elif name.startswith("hinge_"):
            mat = TONES["hinge"]
        elif name.startswith("clasp_"):
            mat = TONES["clasp"]
        elif name.startswith("tray_rib_"):
            mat = TONES["rib"]
    obj.data.materials.append(mat)
    if name.startswith(tuple(cfg.get("smooth_prefixes", ()))):
        obj.data.polygons.foreach_set("use_smooth",
                                      [True] * len(obj.data.polygons))
        obj.data.update()

# --- studio: grey backdrop, key + fill + rim, contact shading -------------
world = bpy.data.worlds.new("w")
world.use_nodes = True
# M4B-B-EVIDENCE-LEGIBILITY: a mid-grey backdrop left a flat elevation of
# mid-grey clay with no silhouette. The backdrop comes from the pinned
# render contract so both families share one policy.
_bd = cfg.get("backdrop_colour", [0.055, 0.055, 0.062])
world.node_tree.nodes["Background"].inputs["Strength"].default_value = \
    cfg.get("backdrop_strength", 0.55)
world.node_tree.nodes["Background"].inputs["Color"].default_value = \
    (_bd[0], _bd[1], _bd[2], 1.0)
scene.world = world


def area(name, loc, rot, sx, sy, energy):
    data = bpy.data.lights.new(name, type="AREA")
    data.shape = "RECTANGLE"
    data.size, data.size_y, data.energy = sx, sy, energy
    obj = bpy.data.objects.new(name, data)
    obj.location, obj.rotation_euler = loc, rot
    scene.collection.objects.link(obj)
    return obj


area("key", (-160, -220, 260), (math.radians(42), 0, math.radians(-36)),
     260, 260, cfg.get("key_energy", 5.2e5))
area("fill", (200, -180, 130), (math.radians(66), 0, math.radians(48)),
     220, 220, cfg.get("fill_energy", 1.5e5))
area("rim", (90, 230, 200), (math.radians(52), 0, math.radians(160)),
     60, 240, cfg.get("rim_energy", 1.15e6))
_r2 = cfg.get("rim2")
if _r2:
    area("rim2", tuple(_r2["loc"]),
         tuple(math.radians(a) for a in _r2["rot_deg"]),
         _r2["size"][0], _r2["size"][1], _r2["energy"])

res_x, res_y = cfg["resolution"]
scene.render.resolution_x = res_x
scene.render.resolution_y = res_y

C = cfg["centre"]
S = cfg["ortho_scale"]
D = cfg.get("camera_distance", 600.0)


def cam(name, loc, rot, scale):
    data = bpy.data.cameras.new(name)
    data.type = "ORTHO"
    data.ortho_scale = scale
    data.sensor_fit = "AUTO"
    data.clip_start = 1.0
    data.clip_end = 20000.0
    obj = bpy.data.objects.new(name, data)
    obj.location, obj.rotation_euler = loc, rot
    scene.collection.objects.link(obj)
    return obj


az, el = math.radians(38), math.radians(26)
cams = {
    "front": cam("front", (C[0], C[1] - D, C[2]), (math.pi / 2, 0, 0), S),
    "top": cam("top", (C[0], C[1], C[2] + D), (0, 0, 0), S),
    "side": cam("side", (C[0] - D, C[1], C[2]),
                (math.pi / 2, 0, -math.pi / 2), S),
    "three_quarter": cam(
        "three_quarter",
        (C[0] + D * math.cos(el) * math.sin(az),
         C[1] - D * math.cos(el) * math.cos(az),
         C[2] + D * math.sin(el)), (math.pi / 2 - el, 0, az), S),
}
for name, v in cfg.get("detail_views", {}).items():
    cams[name] = cam(name, tuple(v["loc"]), tuple(v["rot"]),
                     v.get("scale", S))

for name, out_path in cfg["views"].items():
    scene.camera = cams[name]
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)

# M5 §10: high-precision passes for material characterization. An 8-bit
# PNG quantises exactly where a specular lobe carries its information.
# The EXR is preserved as the scene-linear diagnostic artifact; the 16-bit
# PNG is what the measurement reads, because no EXR reader is installed in
# this environment and claiming a scene-linear measurement that cannot be
# performed would be worse than stating the limit.
for name, out_path in cfg.get("exr_views", {}).items():
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_depth = "32"
    scene.render.image_settings.color_mode = "RGB"
    scene.camera = cams[name]
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    # scene-linear diagnostics, read by Blender itself
    try:
        img = bpy.data.images.load(out_path)
        px = list(img.pixels)
        lum = [(px[i] + px[i + 1] + px[i + 2]) / 3.0
               for i in range(0, len(px), 4)]
        lum.sort()
        n = len(lum)
        print("SCENE_LINEAR_STATS " + json.dumps({
            "view": name,
            "peak_linear_intensity": lum[-1],
            "p999": lum[min(n - 1, int(n * 0.999))],
            "p99": lum[int(n * 0.99)],
            "p50": lum[int(n * 0.50)],
            "p05": lum[int(n * 0.05)],
            "clipping_count": sum(1 for v in lum if v >= 1.0),
            "saturated_pixel_count": sum(1 for v in lum if v >= 0.999),
            "sample_count": n,
        }))
        bpy.data.images.remove(img)
    except Exception as exc:                             # noqa: BLE001
        print(f"SCENE_LINEAR_STATS_FAILED {exc}")

for name, out_path in cfg.get("png16_views", {}).items():
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "16"
    scene.camera = cams[name]
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)

scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "8"

print("PALETTE_CSG_VIEWS_OK")
