"""Deterministic silhouette masks — owner-mandated mask authority.

Silhouettes are NEVER thresholded from shaded RGB renders (lighting-
dependent, grainy, highlight holes). This script renders the meshes with a
flat black emission material on a TRANSPARENT film and outputs RGBA — the
alpha channel is pure geometric coverage: no lights exist in the scene, so
the result is lighting-independent and deterministic by construction.

Cameras replicate the pinned validation_views geometry exactly (same
ortho_scale/positions), so masks are comparable across V1/V2/V3.

Run: Blender -b --factory-startup -noaudio -P silhouette_mask.py -- cfg.json
"""
import json
import math
import sys

import bpy

cfg = json.load(open(sys.argv[sys.argv.index("--") + 1]))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = cfg.get("samples", 16)
scene.cycles.seed = 0
scene.cycles.use_denoising = False
scene.view_settings.view_transform = "Standard"
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.color_depth = "8"
scene.render.film_transparent = True          # alpha = coverage, no bg

objs = {}
for name, path in cfg["meshes"].items():
    bpy.ops.wm.obj_import(filepath=path, forward_axis='Y', up_axis='Z')
    obj = bpy.context.selected_objects[0]
    obj.name = name
    objs[name] = obj

mat = bpy.data.materials.new("MASK_BLACK")
mat.use_nodes = True
nodes = mat.node_tree.nodes
nodes.clear()
em = nodes.new("ShaderNodeEmission")
em.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
out_node = nodes.new("ShaderNodeOutputMaterial")
mat.node_tree.links.new(em.outputs[0], out_node.inputs[0])
for obj in objs.values():
    obj.data.materials.clear()
    obj.data.materials.append(mat)

H = cfg["assembly_height_mm"]
res_x, res_y = cfg["resolution"]
scene.render.resolution_x = res_x
scene.render.resolution_y = res_y
ORTHO_SCALE = H * 1.12
D = 4.0 * H
half = H / 2.0


def cam(name, loc, rot, scale):
    data = bpy.data.cameras.new(name)
    data.type = "ORTHO"
    data.ortho_scale = scale
    data.sensor_fit = "VERTICAL"
    data.clip_start = 1.0
    data.clip_end = 10000.0
    obj = bpy.data.objects.new(name, data)
    obj.location = loc
    obj.rotation_euler = rot
    scene.collection.objects.link(obj)
    return obj


views = {
    "front": cam("front", (0, -D, half), (math.pi / 2, 0, 0), ORTHO_SCALE),
    "side": cam("side", (-D, 0, half), (math.pi / 2, 0, -math.pi / 2),
                ORTHO_SCALE),
    "top": cam("top", (0, 0, H + D), (0, 0, 0), ORTHO_SCALE),
}
for name, view in cfg.get("detail_views", {}).items():
    views[name] = cam(name, (0, -D, view["center_mm"]),
                      (math.pi / 2, 0, 0), view["height_mm"] * 1.6)

for name, out_path in cfg["views"].items():
    scene.camera = views[name]
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)

print("SILHOUETTE_MASK_OK")
