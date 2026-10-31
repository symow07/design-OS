"""P1 V3 material-validation studio — transparent matte orange glass.

Owner-mandated studio setup: neutral grey backdrop, soft key + weaker fill
+ narrow rim, no DoF, Standard colour management, deterministic Cycles CPU
seed 0. The bottle body is the VISUALIZATION_ONLY hollow glass solid with
physically based transmission + amber volume absorption; the frosted
exterior is surface roughness — it softens highlights but never removes
transmission. Collar and bulb are two DISTINCT glossy orange plastics.

Material renders never validate exact geometry silhouette (separate
neutral clay mode exists for that).

Run: Blender -b --factory-startup -noaudio -P p1_material_studio.py -- cfg.json
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
scene.cycles.samples = cfg.get("samples", 128)
scene.cycles.seed = 0
scene.cycles.use_denoising = False
scene.cycles.max_bounces = 20
scene.cycles.transmission_bounces = 16
scene.cycles.transparent_max_bounces = 8
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.cycles.sample_clamp_indirect = 4.0
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "8"
scene.render.film_transparent = False

objs = {}
for name, path in cfg["meshes"].items():
    bpy.ops.wm.obj_import(filepath=path, forward_axis='Y', up_axis='Z')
    obj = bpy.context.selected_objects[0]
    obj.name = name
    objs[name] = obj
    obj.data.polygons.foreach_set("use_smooth",
                                  [True] * len(obj.data.polygons))
    obj.data.update()


def principled(name, **inputs):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    for key, val in inputs.items():
        bsdf.inputs[key].default_value = val
    return mat


# --- glass: transparent amber-tinted, frosted EXTERIOR, volume absorption
glass = bpy.data.materials.new("P1_V3_FROSTED_AMBER_GLASS")
glass.use_nodes = True
gn = glass.node_tree
bsdf = gn.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.97, 0.95, 0.93, 1.0)
bsdf.inputs["Roughness"].default_value = cfg.get("glass_roughness", 0.36)
bsdf.inputs["Transmission Weight"].default_value = 1.0
bsdf.inputs["IOR"].default_value = 1.5
vol = gn.nodes.new("ShaderNodeVolumeAbsorption")
vol.inputs["Color"].default_value = tuple(
    cfg.get("absorption_colour", [0.99, 0.86, 0.70])) + (1.0,)
vol.inputs["Density"].default_value = cfg.get("absorption_density", 0.05)
out_node = gn.nodes["Material Output"]
gn.links.new(vol.outputs[0], out_node.inputs["Volume"])

liquid = bpy.data.materials.new("P1_V4_SERUM_ORANGE")
liquid.use_nodes = True
ln = liquid.node_tree
lb = ln.nodes["Principled BSDF"]
lb.inputs["Base Color"].default_value = (1.0, 0.98, 0.95, 1.0)
lb.inputs["Roughness"].default_value = 0.03
lb.inputs["Transmission Weight"].default_value = 1.0
lb.inputs["IOR"].default_value = 1.36
lvol = ln.nodes.new("ShaderNodeVolumeAbsorption")
lvol.inputs["Color"].default_value = tuple(
    cfg.get("serum_colour", [1.0, 0.66, 0.02])) + (1.0,)
lvol.inputs["Density"].default_value = cfg.get("serum_density", 0.11)
ln.links.new(lvol.outputs[0], ln.nodes["Material Output"].inputs["Volume"])

mats = {
    "glass": glass,
    "liquid": liquid,
    # PLASTIC / GLOSSY / deep saturated burnt orange (dielectric, no
    # transmission)
    "collar": principled("P1_V4_COLLAR_BURNT_ORANGE",
                         **{"Base Color": (0.72, 0.165, 0.012, 1.0),
                            "Roughness": 0.10,
                            "Specular IOR Level": 0.6}),
    # PLASTIC / GLOSSY / OPAQUE deep red-orange — distinct hue + roughness
    "bulb": principled("P1_V4_BULB_RED_ORANGE_OPAQUE",
                       **{"Base Color": (0.70, 0.115, 0.03, 1.0),
                          "Roughness": 0.20,
                          "Specular IOR Level": 0.45}),
}
cm = mats["collar"].node_tree
cbsdf = cm.nodes["Principled BSDF"]
wave = cm.nodes.new("ShaderNodeTexWave")
wave.wave_type = "BANDS"
wave.bands_direction = "X"
wave.inputs["Scale"].default_value = 2.6      # ~60 fine ribs around 21.4
coordc = cm.nodes.new("ShaderNodeTexCoord")
bump = cm.nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.18  # subtle, never exaggerated
bump.inputs["Distance"].default_value = 0.12
cm.links.new(coordc.outputs["Object"], wave.inputs["Vector"])
cm.links.new(wave.outputs["Color"], bump.inputs["Height"])
cm.links.new(bump.outputs["Normal"], cbsdf.inputs["Normal"])

for name, obj in objs.items():
    obj.data.materials.clear()
    obj.data.materials.append(mats[name])

# --- neutral studio -------------------------------------------------------
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.22
world.node_tree.nodes["Background"].inputs["Color"].default_value = \
    (0.5, 0.5, 0.5, 1.0)
scene.world = world

H = cfg["assembly_height_mm"]


def area_light(name, loc, rot, size_x, size_y, energy):
    data = bpy.data.lights.new(name, type="AREA")
    data.shape = "RECTANGLE"
    data.size = size_x
    data.size_y = size_y
    data.energy = energy
    obj = bpy.data.objects.new(name, data)
    obj.location = loc
    obj.rotation_euler = rot
    scene.collection.objects.link(obj)
    return obj


key = area_light("key", (-260, -330, 250), (math.radians(55), 0,
                 math.radians(-38)), 320, 320, 1.3e6)
fill = area_light("fill", (300, -280, 120), (math.radians(72), 0,
                  math.radians(47)), 260, 260, 4.0e5)
rim = area_light("rim", (140, 300, 240), (math.radians(50), 0,
                 math.radians(155)), 60, 260, 1.3e6)

wash = area_light("bg_wash", (0, -60, 420), (math.radians(28), 0, 0),
                  700, 500, 9.0e5)   # lights the backdrop THROUGH which
                                     # the bottle is seen — transmission
                                     # becomes visibly luminous

if cfg.get("lighting") == "side_lit_edge":
    # edge-transmission study: rim-dominant grazing light
    key.data.energy = 1.0e5
    fill.data.energy = 5.0e4
    rim.data.energy = 3.2e6


def flat_material(name, rgb, roughness=1.0):
    return principled(name, **{"Base Color": rgb + (1.0,),
                               "Roughness": roughness,
                               "Specular IOR Level": 0.2})


def make_backdrop(kind):
    mesh = bpy.data.meshes.new("backdrop")
    size = 1400.0
    y = 260.0 if kind in ("grey", "white") else 58.0
    verts = [(-size, y, -300), (size, y, -300), (size, y, 1400),
             (-size, y, 1400)]
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    obj = bpy.data.objects.new("backdrop", mesh)
    scene.collection.objects.link(obj)
    if kind == "grey":
        obj.data.materials.append(flat_material("bg_grey",
                                                (0.60, 0.60, 0.60)))
    elif kind == "white":
        obj.data.materials.append(flat_material("bg_white",
                                                (0.88, 0.88, 0.88)))
    else:                                    # card / stripes: B/W pattern
        mat = bpy.data.materials.new("bg_pattern")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes["Principled BSDF"]
        bsdf.inputs["Roughness"].default_value = 1.0
        tex = nt.nodes.new("ShaderNodeTexChecker")
        tex.inputs["Scale"].default_value = 0.0
        coord = nt.nodes.new("ShaderNodeTexCoord")
        mapping = nt.nodes.new("ShaderNodeMapping")
        if kind == "card":
            # 24 mm checkerboard calibration card
            tex.inputs["Scale"].default_value = 58.0
        else:
            # vertical stripes ~14 mm: stretch checker into bars
            # vertical bars: keep variation along X only (the
            # plane's generated Z axis is collapsed)
            tex.inputs["Scale"].default_value = 130.0
            mapping.inputs["Scale"].default_value = (1.0, 1.0, 0.0001)
        nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        obj.data.materials.append(mat)
    return obj


backdrop = make_backdrop(cfg.get("background", "grey"))

res_x, res_y = cfg["resolution"]
scene.render.resolution_x = res_x
scene.render.resolution_y = res_y
ORTHO_SCALE = H * 1.12
D = 4.0 * H
half = H / 2.0
az, el = math.radians(30), math.radians(12)
TQ = 4.2


def cam_ortho(name, center, scale):
    data = bpy.data.cameras.new(name)
    data.type = "ORTHO"
    data.ortho_scale = scale
    data.sensor_fit = "VERTICAL"
    data.clip_start = 1.0
    data.clip_end = 10000.0
    obj = bpy.data.objects.new(name, data)
    obj.location = (0, -D, center)
    obj.rotation_euler = (math.pi / 2, 0, 0)
    scene.collection.objects.link(obj)
    return obj


def cam_tq(name):
    data = bpy.data.cameras.new(name)
    data.type = "PERSP"
    data.lens = 85
    data.sensor_fit = "VERTICAL"
    data.clip_start = 1.0
    data.clip_end = 10000.0
    obj = bpy.data.objects.new(name, data)
    obj.location = (TQ * H * math.cos(el) * math.sin(az),
                    -TQ * H * math.cos(el) * math.cos(az),
                    half + TQ * H * math.sin(el))
    obj.rotation_euler = (math.pi / 2 - el, 0, az)
    scene.collection.objects.link(obj)
    return obj


cameras = {"front": cam_ortho("front", half, ORTHO_SCALE),
           "three_quarter": cam_tq("tq")}
for name, view in cfg.get("detail_views", {}).items():
    cameras[name] = cam_ortho(name, view["center_mm"],
                              view["height_mm"] * 1.6)

for name, out_path in cfg["views"].items():
    scene.camera = cameras[name]
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)

print("P1_MATERIAL_STUDIO_OK")
