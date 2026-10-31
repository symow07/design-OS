"""PALT-M4 — neutral geometry-validation views for palette assemblies.

Scene built 100% from code, pinned Cycles CPU seed 0, neutral clay only.
No powder realism, no cosmetic colour, no artwork, no beauty lighting.

Run: Blender -b --factory-startup -noaudio -P palette_views.py -- cfg.json
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
scene.cycles.samples = cfg.get("samples", 32)
scene.cycles.seed = 0
scene.cycles.use_denoising = False
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "8"
scene.render.film_transparent = False

objs = []
for name, path in cfg["meshes"].items():
    bpy.ops.wm.obj_import(filepath=path, forward_axis='Y', up_axis='Z')
    obj = bpy.context.selected_objects[0]
    obj.name = name
    objs.append(obj)
    # smooth ONLY curved components; smooth-shading a flat fan-capped slab
    # turns it into a pillow/pyramid (a shading artefact, not geometry)
    smooth_prefixes = tuple(cfg.get("smooth_prefixes", ()))
    if smooth_prefixes and name.startswith(smooth_prefixes):
        obj.data.polygons.foreach_set("use_smooth",
                                      [True] * len(obj.data.polygons))
        obj.data.update()

# neutral validation clay (identical to the RBV standard)
mat = bpy.data.materials.new("VALIDATION_CLAY")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.69, 0.667, 0.65, 1.0)
bsdf.inputs["Roughness"].default_value = 0.9
bsdf.inputs["Specular IOR Level"].default_value = 0.1
for obj in objs:
    obj.data.materials.clear()
    obj.data.materials.append(mat)

world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.85
world.node_tree.nodes["Background"].inputs["Color"].default_value = \
    (0.95, 0.95, 0.945, 1.0)
scene.world = world
sun_data = bpy.data.lights.new("sun", type="SUN")
sun_data.energy = 1.3
sun_data.angle = 0.55
sun = bpy.data.objects.new("sun", sun_data)
sun.rotation_euler = (0.72, 0.16, 0.42)
scene.collection.objects.link(sun)
fill_data = bpy.data.lights.new("fill", type="SUN")
fill_data.energy = 0.45
fill_data.angle = 0.9
fill = bpy.data.objects.new("fill", fill_data)
fill.rotation_euler = (1.1, 0.0, -2.2)
scene.collection.objects.link(fill)

res_x, res_y = cfg["resolution"]
scene.render.resolution_x = res_x
scene.render.resolution_y = res_y

C = cfg["centre"]                 # scene centre (x, y, z)
S = cfg["ortho_scale"]            # shared ortho scale
D = cfg.get("camera_distance", 600.0)


def cam(name, loc, rot, *, ortho=True, scale=None, focal=70.0):
    data = bpy.data.cameras.new(name)
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = scale or S
        data.sensor_fit = "AUTO"
    else:
        data.type = "PERSP"
        data.lens = focal
        data.sensor_fit = "AUTO"
    data.clip_start = 1.0
    data.clip_end = 20000.0
    obj = bpy.data.objects.new(name, data)
    obj.location = loc
    obj.rotation_euler = rot
    scene.collection.objects.link(obj)
    return obj


az, el = math.radians(38), math.radians(26)
cams = {
    "front": cam("front", (C[0], C[1] - D, C[2]), (math.pi / 2, 0, 0)),
    "top": cam("top", (C[0], C[1], C[2] + D), (0, 0, 0)),
    "side": cam("side", (C[0] - D, C[1], C[2]),
                (math.pi / 2, 0, -math.pi / 2)),
    "three_quarter": cam(
        "three_quarter",
        (C[0] + D * math.cos(el) * math.sin(az),
         C[1] - D * math.cos(el) * math.cos(az),
         C[2] + D * math.sin(el)),
        (math.pi / 2 - el, 0, az)),
}
for name, view in cfg.get("detail_views", {}).items():
    cams[name] = cam(name, (view["loc"][0], view["loc"][1], view["loc"][2]),
                     tuple(view["rot"]), scale=view.get("scale", S))

for name, out_path in cfg["views"].items():
    scene.camera = cams[name]
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)

print("PALETTE_VIEWS_OK")
