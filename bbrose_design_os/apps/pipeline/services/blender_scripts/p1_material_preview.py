"""P1 material-reference preview — OWNER_CONFIRMED_MATERIAL_EVIDENCE only.

One three-quarter view mapping the owner-confirmed materials (orange matte
glass bottle, orange plastic collar, transparent plastic bulb). This is a
MATERIAL REFERENCE PREVIEW — it never replaces the neutral geometry-
validation views and is NOT a client-presentation render (no studio
lighting, no luxury grading).

Run: Blender -b --factory-startup -noaudio -P p1_material_preview.py -- cfg.json
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
for name in ("body", "collar", "bulb"):
    path = cfg["meshes"].get(name)
    if not path:
        continue
    bpy.ops.wm.obj_import(filepath=path, forward_axis='Y', up_axis='Z')
    obj = bpy.context.selected_objects[0]
    obj.name = name
    objs[name] = obj


def principled(name, **inputs):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    for key, val in inputs.items():
        bsdf.inputs[key].default_value = val
    return mat


# owner-confirmed material mapping (appearance approximation only).
# V2 owner revision: darker amber-orange frosted glass with VISIBLE light
# transmission; collar and bulb are DIFFERENT saturated glossy orange
# shaders (never the same shader as the bottle).
mats = {
    # GLASS / MATTE(FROSTED) / TRANSLUCENT DARKER AMBER-ORANGE
    "body": principled("P1_V2_BOTTLE_FROSTED_AMBER_GLASS",
                       **{"Base Color": (0.58, 0.20, 0.045, 1.0),
                          "Roughness": 0.42,
                          "Transmission Weight": 0.80,
                          "IOR": 1.5}),
    # PLASTIC / GLOSSY / SATURATED ORANGE
    "collar": principled("P1_V2_COLLAR_SATURATED_ORANGE",
                         **{"Base Color": (0.90, 0.26, 0.015, 1.0),
                            "Roughness": 0.10,
                            "Specular IOR Level": 0.6}),
    # PLASTIC / GLOSSY / SATURATED ORANGE / OPAQUE (distinct shader)
    "bulb": principled("P1_V2_BULB_SATURATED_ORANGE_OPAQUE",
                       **{"Base Color": (0.93, 0.33, 0.05, 1.0),
                          "Roughness": 0.20,
                          "Specular IOR Level": 0.45}),
}
for name, obj in objs.items():
    obj.data.materials.clear()
    obj.data.materials.append(mats[name])
    obj.data.polygons.foreach_set(
        "use_smooth", [True] * len(obj.data.polygons))
    obj.data.update()

world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
world.node_tree.nodes["Background"].inputs["Color"].default_value = \
    (0.96, 0.96, 0.955, 1.0)
scene.world = world
sun_data = bpy.data.lights.new("sun", type="SUN")
sun_data.energy = 1.6
sun_data.angle = 0.6
sun = bpy.data.objects.new("sun", sun_data)
sun.rotation_euler = (0.7, 0.15, 0.4)
scene.collection.objects.link(sun)

H = cfg["assembly_height_mm"]
res_x, res_y = cfg["resolution"]
scene.render.resolution_x = res_x
scene.render.resolution_y = res_y

az, el = math.radians(30), math.radians(12)
TQ = float(cfg.get("three_quarter_distance_factor", 4.2))
data = bpy.data.cameras.new("tq")
data.type = "PERSP"
data.lens = 85
data.sensor_fit = "VERTICAL"
data.clip_start = 1.0
data.clip_end = 10000.0
cam = bpy.data.objects.new("tq", data)
cam.location = (TQ * H * math.cos(el) * math.sin(az),
                -TQ * H * math.cos(el) * math.cos(az),
                H / 2.0 + TQ * H * math.sin(el))
cam.rotation_euler = (math.pi / 2 - el, 0, az)
scene.collection.objects.link(cam)
scene.camera = cam
scene.render.filepath = cfg["output"]
bpy.ops.render.render(write_still=True)
print("P1_MATERIAL_PREVIEW_OK")
