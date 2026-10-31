"""PALT-M4B-A — Boolean-free diagnostic views of the deterministic tray.

This script contains NO Boolean machinery. The recesses arrive already
cut, as real triangles, from the Python kernel. If a caller passes a
``csg`` key it is rejected rather than honoured: the owner's decision is
that Blender Boolean modifiers are NOT_AUTHORITY_FOR_CORE_TRAY_GEOMETRY,
and a silent fallback is exactly what must not exist.

Run: Blender -b --factory-startup -noaudio -P m4b_a_tray_views.py -- cfg.json
"""
import json
import math
import sys

import bpy

cfg = json.load(open(sys.argv[sys.argv.index("--") + 1]))

if cfg.get("csg"):
    raise RuntimeError(
        "M4B-A renders are Boolean-free: PALETTE_TRAY_GEOMETRY_AUTHORITY is "
        "DETERMINISTIC_PYTHON_MESH_CONSTRUCTION and BLENDER_BOOLEAN_MODIFIERS "
        "is NOT_AUTHORITY_FOR_CORE_TRAY_GEOMETRY")

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
    bpy.ops.object.select_all(action="DESELECT")
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path, forward_axis='Y', up_axis='Z')
    new = [o for o in bpy.data.objects if o not in before]
    if len(new) != 1:
        raise RuntimeError(f"import of {name} produced {len(new)} objects")
    obj = new[0]
    obj.name = name
    objs[name] = obj

for mod in ("BOOLEAN",):                      # belt and braces
    for obj in objs.values():
        if any(m.type == mod for m in obj.modifiers):
            raise RuntimeError(f"{obj.name} carries a {mod} modifier")


def clay(name, rgb, rough=0.62):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgb + (1.0,)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = 0.32
    return mat


def wire_mat():
    """Emission through a Wireframe node — deterministic, no modifier."""
    mat = bpy.data.materials.new("WIREFRAME")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    base = nt.nodes.new("ShaderNodeBsdfDiffuse")
    base.inputs["Color"].default_value = (0.90, 0.90, 0.91, 1.0)
    line = nt.nodes.new("ShaderNodeEmission")
    line.inputs["Color"].default_value = (0.05, 0.09, 0.16, 1.0)
    line.inputs["Strength"].default_value = 1.0
    wire = nt.nodes.new("ShaderNodeWireframe")
    wire.use_pixel_size = True
    wire.inputs["Size"].default_value = cfg.get("wire_px", 1.1)
    nt.links.new(wire.outputs["Fac"], mix.inputs["Fac"])
    nt.links.new(base.outputs["BSDF"], mix.inputs[1])
    nt.links.new(line.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def normal_mat():
    """World-space normal direction as colour: proves outward orientation
    (up = green-ish, outward = red/blue), and any inverted face reads as
    its complement."""
    mat = bpy.data.materials.new("NORMALS")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    madd = nt.nodes.new("ShaderNodeVectorMath")
    madd.operation = "MULTIPLY_ADD"
    madd.inputs[1].default_value = (0.5, 0.5, 0.5)
    madd.inputs[2].default_value = (0.5, 0.5, 0.5)
    nt.links.new(geo.outputs["Normal"], madd.inputs[0])
    nt.links.new(madd.outputs["Vector"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


NEUTRAL = clay("NEUTRAL_MEDIUM_GREY_CLAY", (0.42, 0.42, 0.425))
# A3P: diagnostic markers. Additive — no existing caller names a mesh
# "marker_", so no previously produced evidence can change.
MARKER = clay("TECH_MARKER_RED", (0.78, 0.11, 0.09), 0.28)
PAN_MAT = clay("TECH_PAN", (0.58, 0.59, 0.61), 0.34)
POWDER = clay("TECH_POWDER", (0.28, 0.28, 0.29), 0.96)
MODE = cfg.get("mode", "clay")
OVERRIDE = {"wireframe": wire_mat, "normals": normal_mat}.get(MODE)

for name, obj in objs.items():
    obj.data.materials.clear()
    if name.startswith("marker_"):
        # markers stay solid in wireframe and normals modes too, or the
        # image would not expose the feature it exists to show
        mat = MARKER
    elif OVERRIDE:
        mat = OVERRIDE()
    elif name.startswith("metal_pan_"):
        mat = PAN_MAT
    elif name.startswith("powder_"):
        mat = POWDER
    else:
        mat = NEUTRAL
    obj.data.materials.append(mat)
    # ANGLE-limited smoothing only. Smoothing every polygon of a part that
    # mixes flat and curved surfaces domes the flat ones — the deck and the
    # outer walls pillow, and the crisp moulded edges disappear. Smoothing
    # by angle keeps the pocket walls round and every 90 deg edge sharp.
    if cfg.get("smooth_angle_deg") and not OVERRIDE:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth_by_angle(
            angle=math.radians(cfg["smooth_angle_deg"]))
        obj.select_set(False)

world = bpy.data.worlds.new("w")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Strength"].default_value = 0.30 if MODE == "clay" else 0.9
bg.inputs["Color"].default_value = (0.55, 0.55, 0.56, 1.0)
scene.world = world


def area(name, loc, rot, sx, sy, energy):
    data = bpy.data.lights.new(name, type="AREA")
    data.shape = "RECTANGLE"
    data.size, data.size_y, data.energy = sx, sy, energy
    obj = bpy.data.objects.new(name, data)
    obj.location, obj.rotation_euler = loc, rot
    scene.collection.objects.link(obj)
    return obj


if MODE == "clay":
    # a steep key so the pocket walls throw shadow INTO the recess — the
    # recess depth has to be unmistakable, not inferred
    area("key", (-90, -150, 210), (math.radians(31), 0, math.radians(-31)),
         190, 190, 4.4e5)
    area("fill", (170, -130, 120), (math.radians(63), 0, math.radians(52)),
         200, 200, 9.0e4)
    area("rim", (70, 190, 170), (math.radians(50), 0, math.radians(162)),
         55, 210, 2.6e5)

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


def orbit(name, az_deg, el_deg, scale, target=None, dist=None):
    t = target or C
    az, el = math.radians(az_deg), math.radians(el_deg)
    dd = dist or D
    return cam(name,
               (t[0] + dd * math.cos(el) * math.sin(az),
                t[1] - dd * math.cos(el) * math.cos(az),
                t[2] + dd * math.sin(el)),
               (math.pi / 2 - el, 0, az), scale)


cams = {
    "three_quarter": orbit("three_quarter", 38, 27, S),
    "top": cam("top", (C[0], C[1], C[2] + D), (0, 0, 0), S),
}
for name, v in cfg.get("detail_views", {}).items():
    cams[name] = orbit(name, v.get("az", 38), v.get("el", 27),
                       v.get("scale", S), target=v.get("target"),
                       dist=v.get("distance"))

for name, out_path in cfg["views"].items():
    scene.camera = cams[name]
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)

print("M4B_A_TRAY_VIEWS_OK")
