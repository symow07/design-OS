"""RBV-2B — geometry-validation views, scene built 100% from code.

Run: Blender -b --factory-startup -noaudio -P validation_views.py -- cfg.json
The config carries OBJ paths (body + optional collar/bulb), physical dims,
view list and output dir. Camera/lighting/material follow the approved
standards; nothing reads interactive preferences.
"""
import json
import math
import sys

import bpy

cfg = json.load(open(sys.argv[sys.argv.index("--") + 1]))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# --- §8 pinned colour management / engine ---------------------------------
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = cfg["samples"]
scene.cycles.seed = 0
scene.cycles.use_denoising = False
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "8"
scene.render.film_transparent = False

# --- import meshes (ONE immutable geometry for every view) ----------------
objs = {}
for name in ("body", "collar", "bulb"):
    path = cfg["meshes"].get(name)
    if not path:
        continue
    bpy.ops.wm.obj_import(filepath=path, forward_axis='Y', up_axis='Z')
    obj = bpy.context.selected_objects[0]
    obj.name = name
    objs[name] = obj

# optional smooth shading (default OFF preserves every existing fixture
# render exactly; loft facets disappear under smooth normals)
if cfg.get("shade_smooth"):
    for obj in objs.values():
        obj.data.polygons.foreach_set(
            "use_smooth", [True] * len(obj.data.polygons))
        obj.data.update()

# --- §7 neutral clay override ---------------------------------------------
mat = bpy.data.materials.new("VALIDATION_CLAY")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.69, 0.667, 0.65, 1.0)
bsdf.inputs["Roughness"].default_value = 0.9
bsdf.inputs["Specular IOR Level"].default_value = 0.1
for obj in objs.values():
    obj.data.materials.clear()
    obj.data.materials.append(mat)

# --- §6 geometry-validation lighting --------------------------------------
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
world.node_tree.nodes["Background"].inputs["Color"].default_value = \
    (0.96, 0.96, 0.955, 1.0)
scene.world = world
sun_data = bpy.data.lights.new("sun", type="SUN")
sun_data.energy = 1.2
sun_data.angle = 0.6
sun = bpy.data.objects.new("sun", sun_data)
sun.rotation_euler = (0.7, 0.15, 0.4)
scene.collection.objects.link(sun)

H = cfg["assembly_height_mm"]
CZ = cfg["closure_center_mm"]
CH = cfg["closure_height_mm"]
res_x, res_y = cfg["resolution"]
scene.render.resolution_x = res_x
scene.render.resolution_y = res_y

ORTHO_SCALE = H * 1.12          # shared vertical scale: front/side/top


def cam(name, loc, rot, *, ortho=True, scale=None, focal=None):
    data = bpy.data.cameras.new(name)
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = scale
        data.sensor_fit = "VERTICAL"     # ortho_scale binds the vertical
    else:
        data.type = "PERSP"
        data.lens = focal
        data.sensor_fit = "VERTICAL"
    data.clip_start = 1.0
    data.clip_end = 10000.0
    obj = bpy.data.objects.new(name, data)
    obj.location = loc
    obj.rotation_euler = rot
    scene.collection.objects.link(obj)
    return obj


D = 4.0 * H
half = H / 2.0
az, el = math.radians(30), math.radians(12)
# taller assemblies need a farther three-quarter camera; default preserves
# every existing fixture render exactly
TQ = float(cfg.get("three_quarter_distance_factor", 3.2))
views = {
    "front": cam("front", (0, -D, half), (math.pi / 2, 0, 0),
                 scale=ORTHO_SCALE),
    "side": cam("side", (-D, 0, half), (math.pi / 2, 0, -math.pi / 2),
                scale=ORTHO_SCALE),
    "top": cam("top", (0, 0, H + D), (0, 0, 0), scale=ORTHO_SCALE),
    "closure_detail": cam("closure", (0, -D, CZ), (math.pi / 2, 0, 0),
                          scale=CH * 1.6),
    "three_quarter_diagnostic": cam(
        "three_quarter",
        (TQ * H * math.cos(el) * math.sin(az),
         -TQ * H * math.cos(el) * math.cos(az),
         half + TQ * H * math.sin(el)),
        (math.pi / 2 - el, 0, az), ortho=False, focal=85),
}


def render(view, out):
    scene.camera = views[view] if view in views else views["front"]
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)


for view in ("front", "side", "top", "closure_detail",
             "three_quarter_diagnostic"):
    if view in cfg["views"]:
        render(view, cfg["views"][view])

# --- wireframe view --------------------------------------------------------
if "wireframe" in cfg["views"]:
    wire_mat = bpy.data.materials.new("WIRE")
    wire_mat.use_nodes = True
    nodes = wire_mat.node_tree.nodes
    nodes.clear()
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.05, 0.05, 0.06, 1.0)
    out_node = nodes.new("ShaderNodeOutputMaterial")
    wire_mat.node_tree.links.new(em.outputs[0], out_node.inputs[0])
    for obj in objs.values():
        mod = obj.modifiers.new("wire", "WIREFRAME")
        mod.thickness = H * 0.0025
        mod.use_replace = True
        obj.data.materials.clear()
        obj.data.materials.append(wire_mat)
    render("front", cfg["views"]["wireframe"])
    for obj in objs.values():
        obj.modifiers.clear()
        obj.data.materials.clear()
        obj.data.materials.append(mat)

# --- normals-orientation view (normal → RGB emission) ----------------------
if "normals" in cfg["views"]:
    nmat = bpy.data.materials.new("NORMALS")
    nmat.use_nodes = True
    nodes = nmat.node_tree.nodes
    nodes.clear()
    geo = nodes.new("ShaderNodeNewGeometry")
    vmath = nodes.new("ShaderNodeVectorMath")
    vmath.operation = "MULTIPLY_ADD"
    vmath.inputs[1].default_value = (0.5, 0.5, 0.5)
    vmath.inputs[2].default_value = (0.5, 0.5, 0.5)
    em = nodes.new("ShaderNodeEmission")
    out_node = nodes.new("ShaderNodeOutputMaterial")
    links = nmat.node_tree.links
    links.new(geo.outputs["Normal"], vmath.inputs[0])
    links.new(vmath.outputs[0], em.inputs["Color"])
    links.new(em.outputs[0], out_node.inputs[0])
    for obj in objs.values():
        obj.data.materials.clear()
        obj.data.materials.append(nmat)
    render("front", cfg["views"]["normals"])

print("VALIDATION_VIEWS_OK")
