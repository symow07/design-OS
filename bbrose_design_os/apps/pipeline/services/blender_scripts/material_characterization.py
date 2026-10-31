"""M5 §1/§2/§4 — the material characterization rig and its measurement.

Two things this script exists to do that the production view script
cannot.

*Excite a specular lobe.* The production rig uses broad soft sources,
which is right for reading form and wrong for reading a BRDF: it produced
SPECULAR_TO_DIFFUSE_RATIO ~1.1, essentially pure diffuse, so five of six
discriminators had no signal. This rig keeps a broad source for the
diffuse base and adds a COMPACT source to produce a measurable
reflection.

*Measure in scene-linear.* Blender has the float Render Result before any
display conversion, so the numbers come from here rather than from a PNG.
The JSON this writes is the numerical authority; the PNG beside it is
human-review evidence and is never described as scene-linear.

Regions are read from a mask rendered once from the same geometry and
camera, so a measurement can say which surface it came from without
guessing at image rows.

Run: Blender -b --factory-startup -noaudio -P material_characterization.py -- cfg.json
"""
import json
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import powder_materials  # noqa: E402 — M6 structural powder graphs

cfg = json.load(open(sys.argv[sys.argv.index("--") + 1]))

# --------------------------------------------------------------------------
# scene
# --------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = cfg.get("samples", 64)
scene.cycles.seed = 0
scene.cycles.use_denoising = False
# fireflies from a compact bright source would make the measurement
# unstable, so clamp indirect rather than denoise the evidence
scene.cycles.sample_clamp_indirect = cfg.get("clamp_indirect", 4.0)
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "8"
scene.render.film_transparent = False
scene.render.resolution_x, scene.render.resolution_y = cfg["resolution"]

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
    for poly in obj.data.polygons:
        poly.use_smooth = name in cfg.get("smooth_regions", [])

# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------


def principled(name, spec):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    rgb = spec.get("display_rgb") or [0.62, 0.62, 0.63]
    b.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    b.inputs["Roughness"].default_value = spec.get("roughness", 0.55)
    b.inputs["Metallic"].default_value = spec.get("metallic", 0.0)
    trans = spec.get("transmission", 0.0)
    if trans:
        b.inputs["Transmission Weight"].default_value = trans
        b.inputs["IOR"].default_value = spec.get("ior", 1.49)
    if spec.get("sheen"):
        b.inputs["Sheen Weight"].default_value = spec["sheen"]
    if spec.get("clearcoat"):
        b.inputs["Coat Weight"].default_value = spec["clearcoat"]
    b.inputs["Specular IOR Level"].default_value = 0.5
    return mat


def emission(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


MASK_MODE = bool(cfg.get("mask_mode"))
spec = cfg.get("material", {})
region_colours = cfg.get("region_colours", {})

for name, obj in objs.items():
    obj.data.materials.clear()
    if MASK_MODE:
        obj.data.materials.append(
            emission(f"MASK_{name}", region_colours.get(name,
                                                        [1.0, 1.0, 1.0])))
    elif spec.get("powder_family"):
        obj.data.materials.append(
            powder_materials.build(name, spec))
    else:
        obj.data.materials.append(principled(f"MAT_{name}", spec))

# --------------------------------------------------------------------------
# §1/§2 — lighting: broad diffuse + COMPACT specular + restrained fill
# --------------------------------------------------------------------------
world = bpy.data.worlds.new("w")
world.use_nodes = True
bg = cfg.get("backdrop_colour", [0.05, 0.05, 0.055])
world.node_tree.nodes["Background"].inputs["Color"].default_value = \
    (bg[0], bg[1], bg[2], 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = \
    0.0 if MASK_MODE else cfg.get("backdrop_strength", 0.25)
scene.world = world


def area(name, loc, rot, sx, sy, energy):
    data = bpy.data.lights.new(name, type="AREA")
    data.shape = "RECTANGLE"
    data.size, data.size_y, data.energy = sx, sy, energy
    o = bpy.data.objects.new(name, data)
    o.location, o.rotation_euler = loc, rot
    scene.collection.objects.link(o)
    return o


def spherical(dist, az_deg, el_deg, centre):
    az, el = math.radians(az_deg), math.radians(el_deg)
    return (centre[0] + dist * math.cos(el) * math.sin(az),
            centre[1] - dist * math.cos(el) * math.cos(az),
            centre[2] + dist * math.sin(el))


C = cfg["centre"]


def emissive_panel(name, loc, rot, sx, sy, strength):
    """A neutral emissive plane — something for a metal to reflect.

    §3: the reflection environment is deterministic geometry with pinned
    luminances, not an HDRI of uncertain content or licence.
    """
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = (sx, sy, 1.0)
    mat = bpy.data.materials.new(f"ENV_{name}")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    o.data.materials.append(mat)
    # panels illuminate and appear in reflections but must not occlude the
    # camera's direct view of the swatch; they are placed off-axis by cfg
    return o


for pn in cfg.get("environment_panels", []):
    loc = spherical(pn["distance"], pn["azimuth"], pn["elevation"], C)
    rot = (math.radians(90 - pn["elevation"]), 0,
           math.radians(pn["azimuth"]))
    emissive_panel(pn["name"], loc, rot, pn["size"][0], pn["size"][1],
                   0.0 if MASK_MODE else pn["emission"])

for st in cfg.get("background_strips", []):
    loc = spherical(st["distance"], st["azimuth"], st["elevation"], C)
    rot = (math.radians(90 - st["elevation"]), 0,
           math.radians(st["azimuth"]))
    # a bank of alternating bright/dark strips — the transmission target
    n = st["count"]
    pattern = st.get("pattern") or [k % 2 == 0 for k in range(n)]
    for k in range(n):
        off = (k - (n - 1) / 2.0) * st["pitch"]
        ax = math.radians(st["azimuth"])
        sloc = (loc[0] + off * math.cos(ax), loc[1] + off * math.sin(ax),
                loc[2])
        emissive_panel(f"{st['name']}_{k}", sloc, rot,
                       st["strip_width"], st["strip_height"],
                       0.0 if MASK_MODE else
                       (st["bright"] if pattern[k] else st["dark"]))

if cfg.get("floor_panel") and not MASK_MODE:
    f = cfg["floor_panel"]
    bpy.ops.mesh.primitive_plane_add(
        size=1.0, location=(C[0], C[1], C[2] + f["z_offset"]))
    o = bpy.context.active_object
    o.name = "neutral_floor"
    o.scale = (f["size"], f["size"], 1.0)
    fm = bpy.data.materials.new("FLOOR")
    fm.use_nodes = True
    fb = fm.node_tree.nodes["Principled BSDF"]
    fb.inputs["Base Color"].default_value = (f["grey"], f["grey"],
                                             f["grey"], 1.0)
    fb.inputs["Roughness"].default_value = 0.8
    o.data.materials.append(fm)

if cfg.get("hide_swatch"):
    # the reference pass: the environment/target alone, measured over the
    # same pixel regions the swatch would occupy
    for o in objs.values():
        o.hide_render = True

if not MASK_MODE:
    d = cfg["diffuse_source"]
    area("broad_diffuse", spherical(d["distance"], d["azimuth"],
                                    d["elevation"], C),
         (math.radians(90 - d["elevation"]), 0, math.radians(d["azimuth"])),
         d["size"], d["size"], d["energy"])

    s = cfg["specular_source"]
    area("compact_specular", spherical(s["distance"], s["azimuth"],
                                       s["elevation"], C),
         (math.radians(90 - s["elevation"]), 0, math.radians(s["azimuth"])),
         s["size"], s["size"], s["energy"])

    f = cfg.get("fill_source")
    if f and f.get("energy"):
        area("fill", spherical(f["distance"], f["azimuth"], f["elevation"],
                               C),
             (math.radians(90 - f["elevation"]), 0,
              math.radians(f["azimuth"])),
             f["size"], f["size"], f["energy"])

# --------------------------------------------------------------------------
# camera
# --------------------------------------------------------------------------
cam_cfg = cfg["camera"]
data = bpy.data.cameras.new("characterization")
data.type = "ORTHO"
data.ortho_scale = cam_cfg["ortho_scale"]
data.clip_start, data.clip_end = 1.0, 20000.0
cam = bpy.data.objects.new("characterization", data)
cam.location = spherical(cam_cfg["distance"], cam_cfg["azimuth"],
                         cam_cfg["elevation"], C)
cam.rotation_euler = (math.radians(90 - cam_cfg["elevation"]), 0,
                      math.radians(cam_cfg["azimuth"]))
scene.collection.objects.link(cam)
scene.camera = cam

scene.render.filepath = cfg["png"]
bpy.ops.render.render(write_still=True)

if cfg.get("png16"):
    # M6: a dim-but-valid frame quantises away at 8 bits; the census
    # reads this 16-bit copy so the rig's calibrated energy cannot
    # crush event contrast into quantisation noise.
    scene.render.image_settings.color_depth = "16"
    bpy.data.images["Render Result"].save_render(filepath=cfg["png16"])
    scene.render.image_settings.color_depth = "8"

# --------------------------------------------------------------------------
# §4 — scene-linear measurement, straight from the float Render Result
# --------------------------------------------------------------------------


def render_pixels():
    """Float RGBA from the render result, before display conversion."""
    img = bpy.data.images["Render Result"]
    # Render Result pixels are not directly readable; save and reload as
    # EXR, which preserves the float values exactly.
    exr = cfg["exr"]
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_depth = "32"
    img.save_render(filepath=exr)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "8"
    loaded = bpy.data.images.load(exr)
    px = list(loaded.pixels)
    w, h = loaded.size
    bpy.data.images.remove(loaded)
    return px, w, h


def luminance(px, count):
    return [(px[i * 4] * 0.2126 + px[i * 4 + 1] * 0.7152
             + px[i * 4 + 2] * 0.0722) for i in range(count)]


def percentiles(sorted_vals, ps):
    n = len(sorted_vals)
    if n == 0:
        return {str(p): 0.0 for p in ps}
    return {str(p): sorted_vals[min(n - 1, max(0, int(n * p / 100.0)))]
            for p in ps}


px, W, H = render_pixels()
lum = luminance(px, W * H)

if MASK_MODE:
    # the mask render itself is the artifact; emit the pixel classes so the
    # caller can build region indices deterministically
    rgb = [(round(px[i * 4], 4), round(px[i * 4 + 1], 4),
            round(px[i * 4 + 2], 4)) for i in range(W * H)]
    json.dump({"mode": "MASK", "width": W, "height": H,
               "region_colours": region_colours,
               "rgb": rgb},
              open(cfg["measurements"], "w"))
    print("MATERIAL_CHARACTERIZATION_OK")
    sys.exit(0)

regions = cfg.get("region_indices", {})
out_regions = {}
for region, idxs in regions.items():
    vals = sorted(lum[i] for i in idxs if i < len(lum))
    if not vals:
        continue
    n = len(vals)
    mean = sum(vals) / n
    med = vals[n // 2]
    pk = vals[min(n - 1, int(n * 0.999))]
    half = med + 0.5 * (pk - med)
    grid = None
    if cfg.get("region_grids"):
        G = 32
        xs = [i % W for i in idxs]
        ys = [i // W for i in idxs]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        acc = [[0.0] * G for _ in range(G)]
        cnt = [[0] * G for _ in range(G)]
        for i in idxs:
            if i >= len(lum):
                continue
            gx = min(G - 1, int((i % W - x0) * G / max(1, x1 - x0 + 1)))
            gy = min(G - 1, int((i // W - y0) * G / max(1, y1 - y0 + 1)))
            acc[gy][gx] += lum[i]
            cnt[gy][gx] += 1
        grid = [[round(acc[r][c] / cnt[r][c], 6) if cnt[r][c] else 0.0
                 for c in range(G)] for r in range(G)]
    out_regions[region] = {
        "grid": grid,
        "sample_count": n,
        "scene_linear_mean": mean,
        "scene_linear_median": med,
        "scene_linear_peak": vals[-1],
        "scene_linear_p999": pk,
        "percentiles": percentiles(vals, [5, 25, 50, 75, 95, 99]),
        "clipped_sample_count": sum(1 for v in vals if v >= 1.0),
        "saturated_sample_count": sum(1 for v in vals if v >= 0.999),
        "highlight_fwhm_fraction": sum(1 for v in vals if v > half) / n,
        "specular_to_diffuse_ratio": pk / med if med > 1e-9 else 0.0,
        "highlight_profile_samples": [
            vals[min(n - 1, int(n * q))]
            for q in (0.50, 0.75, 0.90, 0.95, 0.99, 0.999)],
    }

all_vals = sorted(v for v in lum if v > 0.0)
json.dump({
    "mode": "MEASURE",
    "schema": "material_scene_linear_measurement/1.0",
    "measured_in": "SCENE_LINEAR",
    "source": "Blender float Render Result before display conversion",
    "width": W, "height": H,
    "render_identity": cfg.get("render_identity"),
    "material_identity": cfg.get("material_identity"),
    "geometry_identity": cfg.get("geometry_identity"),
    "camera_identity": cfg.get("camera_identity"),
    "lighting_contract_identity": cfg.get("lighting_contract_identity"),
    "regions": out_regions,
    "frame": {
        "scene_linear_peak": all_vals[-1] if all_vals else 0.0,
        "scene_linear_mean": (sum(all_vals) / len(all_vals))
        if all_vals else 0.0,
        "percentiles": percentiles(all_vals, [5, 50, 95, 99]),
        "clipped_sample_count": sum(1 for v in all_vals if v >= 1.0),
        "saturated_sample_count": sum(1 for v in all_vals if v >= 0.999),
    },
}, open(cfg["measurements"], "w"), indent=1)

print("MATERIAL_CHARACTERIZATION_OK")
