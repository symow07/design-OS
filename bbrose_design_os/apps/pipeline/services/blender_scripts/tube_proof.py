"""[His answer after test day finding 3, 2026-09-30, step 3; his look at 117 drawn from its map, 2026-10-02: "And also the
3D".] Blender: the squeeze tube's mesh (``tube_proof.tube_mesh``, an OBJ of millimetres, y up, z toward the viewer) with
the drawing wrapped on it, under a gloss, on its ground — rendered from the front and turned a little, side by side.
Run as ``blender -b --factory-startup -noaudio -P tube_proof.py -- cfg.json``; prints TUBE_PROOF_OK."""
import json
import math
import sys

import bpy

cfg = json.load(open(sys.argv[sys.argv.index("--") + 1]))
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

verts, uvs, faces = [], [], []
for line in open(cfg["obj"]):
    parts = line.split()
    if not parts:
        continue
    if parts[0] == "v":
        x, y, z = (float(v) / 1000.0 for v in parts[1:4])
        verts.append((x, -z, y))                       # Blender: z up, the viewer at -y
    elif parts[0] == "vt":
        uvs.append((float(parts[1]), float(parts[2])))
    elif parts[0] == "f":
        faces.append([tuple(int(i) - 1 for i in p.split("/")) for p in parts[1:]])
mesh = bpy.data.meshes.new("tube")
mesh.from_pydata(verts, [], [[vi for vi, _ti in f] for f in faces])
layer = mesh.uv_layers.new(name="drawing")
loop = 0
for f in faces:
    for _vi, ti in f:
        layer.data[loop].uv = uvs[ti]
        loop += 1
for poly in mesh.polygons:
    poly.use_smooth = True
tube = bpy.data.objects.new("tube", mesh)
scene.collection.objects.link(tube)

mat = bpy.data.materials.new("sleeve")
mat.use_nodes = True
nodes, links = mat.node_tree.nodes, mat.node_tree.links
bsdf = nodes["Principled BSDF"]
tex = nodes.new("ShaderNodeTexImage")
tex.image = bpy.data.images.load(cfg["artwork"])
tex.interpolation = "Cubic"
links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.35
for name, value in (("Coat Weight", 0.45), ("Coat Roughness", 0.05), ("Specular IOR Level", 0.35)):
    if name in bsdf.inputs:
        bsdf.inputs[name].default_value = value
tube.data.materials.append(mat)

h = cfg["height_mm"] / 1000.0
world = bpy.data.worlds.new("ground")
scene.world = world
world.use_nodes = True
g = cfg["ground"].lstrip("#")
rgb = [((int(g[i:i + 2], 16) / 255.0 + 0.055) / 1.055) ** 2.4 for i in (0, 2, 4)]
world.node_tree.nodes["Background"].inputs["Color"].default_value = (*rgb, 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5
scene.render.film_transparent = True                    # the ground laid under it afterwards, at its own colour


aim = bpy.data.objects.new("aim", None)                  # the tube's middle, every light turned to it
aim.location = (0.0, 0.0, h / 2.0)
scene.collection.objects.link(aim)


def light(name, loc, energy, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.size = energy, size
    obj = bpy.data.objects.new(name, data)
    obj.location = loc
    scene.collection.objects.link(obj)
    track = obj.constraints.new("TRACK_TO")
    track.target, track.track_axis, track.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"


light("key", (-0.35, -0.45, h * 0.9), 2.2, 0.35)
light("fill", (0.4, -0.35, h * 0.5), 0.9, 0.5)
light("rim", (0.0, 0.4, h * 1.1), 1.5, 0.3)

cam_data = bpy.data.cameras.new("camera")
cam_data.lens = 85.0
cam = bpy.data.objects.new("camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
scene.render.engine = "CYCLES"
scene.cycles.samples = int(cfg["samples"])
scene.cycles.device = "CPU"
scene.render.resolution_x, scene.render.resolution_y = cfg["resolution"]
scene.view_settings.view_transform = "Standard"
distance = h * 3.1
outs = []
for name, turn in (("front", 0.0), ("turned", 22.0)):
    t = math.radians(turn)
    cam.location = (distance * math.sin(t), -distance * math.cos(t), h / 2.0)
    cam.rotation_euler = (math.pi / 2, 0.0, t)
    path = cfg["out"].replace(".png", "_%s.png" % name)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    outs.append(path)
print("TUBE_PROOF_OK", json.dumps(outs))
