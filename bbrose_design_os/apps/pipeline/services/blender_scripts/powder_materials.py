"""M6 §§4-12 — structural powder node graphs, shared by both render
scripts (product views and characterization).

Nine families, nine DIFFERENT graphs. The structural spine:

- MATTE/SATIN/PRESSED carry real bump microstructure — the grazing
  response comes from geometry-level normals, never colour+roughness
  alone (§4).
- SHIMMER/METALLIC are per-cell Voronoi flake fields: every cell is one
  flake with its own facet normal and reflectivity. Shimmer is sparse
  fine sparkle over powder; metallic is a near-total dense field that
  reads as a coherent metal highlight (§6/§7) — same construction, a
  physically different census, and the census is the family.
- GLITTER is the same per-cell construction at RESOLVABLE particle
  scale with sparse coverage: each lit cell is one discrete visible
  particle with an individual facet direction (§8). Deterministic
  cells with individual facets, not brightness noise.
- BAKED is crust-over-dome: the dome itself is GEOMETRY (built by the
  powder-volume builder, not here); this graph only supplies the
  vitrified crust (§9).
- MARBLED mixes 2-3 derived colour components through an
  object-attached warped noise — coordinates are object space, so the
  pattern is pinned to the powder volume and cannot swim with the
  camera (§10).
- PRESSED adds the compaction ring in Generated (bounding-box) space so
  it stays centred on any pan shape (§11).
- CREAM has NO granular structure at all — its distinction is the
  absence (§12).

Every texture is seeded through the 4D W channel from the spec's
deterministic seed; Cycles seed stays 0 in both host scripts.
"""
import bpy


def _new(nt, kind):
    return nt.nodes.new(kind)


def _coords(nt, seed):
    """Object-space coordinates, offset by the deterministic seed."""
    tc = _new(nt, "ShaderNodeTexCoord")
    off = _new(nt, "ShaderNodeVectorMath")
    off.operation = "ADD"
    s = float(seed)
    off.inputs[1].default_value = (s * 7.13, s * 3.71, s * 1.97)
    nt.links.new(tc.outputs["Object"], off.inputs[0])
    return off.outputs["Vector"]


def _w(seed):
    return float(seed) * 0.7311


def _noise(nt, vec, *, scale_mm, seed, detail=3.0, distortion=0.0):
    n = _new(nt, "ShaderNodeTexNoise")
    n.noise_dimensions = "4D"
    n.inputs["Scale"].default_value = 1.0 / max(scale_mm, 1e-4)
    n.inputs["W"].default_value = _w(seed)
    n.inputs["Detail"].default_value = detail
    if "Distortion" in n.inputs:
        n.inputs["Distortion"].default_value = distortion
    nt.links.new(vec, n.inputs["Vector"])
    return n


def _voronoi(nt, vec, *, scale_mm, seed, distance="EUCLIDEAN"):
    v = _new(nt, "ShaderNodeTexVoronoi")
    v.voronoi_dimensions = "4D"
    v.feature = "F1"
    v.distance = distance
    v.inputs["Scale"].default_value = 1.0 / max(scale_mm, 1e-4)
    v.inputs["W"].default_value = _w(seed)
    v.inputs["Randomness"].default_value = 1.0
    nt.links.new(vec, v.inputs["Vector"])
    return v


def _cell_random(nt, voronoi):
    """One deterministic scalar in [0,1) per Voronoi cell."""
    sep = _new(nt, "ShaderNodeSeparateColor")
    nt.links.new(voronoi.outputs["Color"], sep.inputs["Color"])
    return sep.outputs["Red"]


def _math(nt, op, a, b=None, value=None):
    m = _new(nt, "ShaderNodeMath")
    m.operation = op
    if hasattr(a, "node"):
        nt.links.new(a, m.inputs[0])
    else:
        m.inputs[0].default_value = a
    if b is not None:
        if hasattr(b, "node"):
            nt.links.new(b, m.inputs[1])
        else:
            m.inputs[1].default_value = b
    if value is not None:
        m.inputs[1].default_value = value
    return m.outputs["Value"]


def _bump(nt, height, amplitude, *, scale_mm=0.3, normal_in=None,
          law="AMPLITUDE_TIMES_SCALE_MM"):
    """Micro-relief with a PHYSICAL height.

    The original realization set only Strength and left Distance at
    its default, which renders fine powder grain invisibly — proven by
    a parameter sweep against a flat control. Amplitude now maps to
    the Bump DISTANCE as a real height (amplitude x grain scale, in
    scene mm), with Strength fixed at 1.0, so a contract amplitude is
    a physical quantity rather than a unitless knob that quietly does
    nothing.
    """
    if law != "AMPLITUDE_TIMES_SCALE_MM":
        raise ValueError(f"undeclared bump distance law {law!r}")
    b = _new(nt, "ShaderNodeBump")
    b.inputs["Strength"].default_value = 1.0
    b.inputs["Distance"].default_value = max(amplitude * scale_mm, 0.0)
    nt.links.new(height, b.inputs["Height"])
    if normal_in is not None:
        nt.links.new(normal_in, b.inputs["Normal"])
    return b.outputs["Normal"]


def _facet_normal(nt, voronoi, jitter):
    """A per-cell facet: geometry normal tilted by the cell's own
    deterministic random vector. Each flake/particle catches light in
    its own direction — the mechanism behind discrete glints."""
    geo = _new(nt, "ShaderNodeNewGeometry")
    half = _new(nt, "ShaderNodeVectorMath")
    half.operation = "SUBTRACT"
    nt.links.new(voronoi.outputs["Color"], half.inputs[0])
    half.inputs[1].default_value = (0.5, 0.5, 0.5)
    scaled = _new(nt, "ShaderNodeVectorMath")
    scaled.operation = "SCALE"
    nt.links.new(half.outputs["Vector"], scaled.inputs[0])
    scaled.inputs["Scale"].default_value = jitter
    added = _new(nt, "ShaderNodeVectorMath")
    added.operation = "ADD"
    nt.links.new(geo.outputs["Normal"], added.inputs[0])
    nt.links.new(scaled.outputs["Vector"], added.inputs[1])
    norm = _new(nt, "ShaderNodeVectorMath")
    norm.operation = "NORMALIZE"
    nt.links.new(added.outputs["Vector"], norm.inputs[0])
    return norm.outputs["Vector"]


def _mix_rgb(nt, fac, a_rgb, b_rgb):
    m = _new(nt, "ShaderNodeMix")
    m.data_type = "RGBA"
    if hasattr(fac, "node"):
        nt.links.new(fac, m.inputs["Factor"])
    else:
        m.inputs["Factor"].default_value = fac
    for sock, val in (("A", a_rgb), ("B", b_rgb)):
        if hasattr(val, "node"):
            nt.links.new(val, m.inputs[sock])
        else:
            m.inputs[sock].default_value = (*val, 1.0)
    return m.outputs["Result"]


def _base(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    b.inputs["Specular IOR Level"].default_value = 0.28
    return mat, mat.node_tree, b


def _mottle_colour(nt, b, rgb, vec, *, scale_mm, strength, seed,
                   detail, seed_offset, distortion):
    """Large-scale value mottling — pressed powder is never one flat
    value. Multiplies the base colour by 1-strength..1."""
    n = _noise(nt, vec, scale_mm=scale_mm, seed=seed + seed_offset,
               detail=detail, distortion=distortion)
    lift = _math(nt, "MULTIPLY", n.outputs["Fac"], strength)
    fac = _math(nt, "ADD", lift, 1.0 - strength)
    mixed = _mix_rgb(nt, fac, (0.0, 0.0, 0.0), rgb)
    nt.links.new(mixed, b.inputs["Base Color"])


# --------------------------------------------------------------------------
# family graphs
# --------------------------------------------------------------------------

def _matte(nt, b, spec, vec):
    """§4 — loose-milled structure from the milling block: coarse
    grain, HIGH-amplitude incoherent micro-normals, broad particle
    distribution realized as extra noise octaves and roughness
    variance. The broad dull lobe comes from the normal field, not
    from a roughness constant."""
    p = spec["params"]
    sh = p["shader"]
    mill = p["milling"]
    micro = _noise(nt, vec, scale_mm=mill["microparticle_scale_mm"],
                   seed=spec["seed"],
                   detail=sh["noise_detail_base"]
                   + sh["noise_detail_variance_coeff"]
                   * mill["microparticle_variance"],
                   distortion=sh["noise_distortion"])
    comp = _noise(nt, vec, scale_mm=p["compression_texture"]["scale_mm"],
                  seed=spec["seed"] + sh["compression_seed_offset"],
                  detail=sh["compression_noise_detail"],
                  distortion=sh["noise_distortion"])
    height = _math(nt, "ADD", micro.outputs["Fac"],
                   _math(nt, "MULTIPLY", comp.outputs["Fac"],
                         p["compression_texture"]["strength"]
                         / max(mill["micronormal_amplitude"], 1e-4)))
    normal = _bump(nt, height, mill["micronormal_amplitude"],
                   scale_mm=mill["microparticle_scale_mm"],
                   law=sh["bump_distance_law"])
    nt.links.new(normal, b.inputs["Normal"])
    rough = _math(nt, "ADD", p["surface_roughness"],
                  _math(nt, "MULTIPLY", micro.outputs["Fac"],
                        sh["roughness_variation_coeff"]
                        * (1.0 + mill["microparticle_variance"])))
    nt.links.new(rough, b.inputs["Roughness"])
    b.inputs["Specular IOR Level"].default_value = \
        sh["specular_ior_level"]
    _mottle_colour(nt, b, spec["display_rgb"], vec,
                   scale_mm=p["macrotexture"]["scale_mm"],
                   strength=p["macrotexture"]["strength"],
                   seed=spec["seed"], detail=sh["mottle_detail"],
                   seed_offset=sh["mottle_seed_offset"],
                   distortion=sh["noise_distortion"])


def _satin(nt, b, spec, vec):
    """§4 — finer-milled structure: small uniform grain at LOW
    amplitude, surface smoothing tightening the effective lobe, and a
    coherent low sheen riding on that uniformity. Still powder — the
    grain exists, it is just fine — never glossy plastic."""
    p = spec["params"]
    sh = p["shader"]
    mill = p["milling"]
    micro = _noise(nt, vec, scale_mm=mill["microparticle_scale_mm"],
                   seed=spec["seed"],
                   detail=sh["noise_detail_base"]
                   + sh["noise_detail_variance_coeff"]
                   * mill["microparticle_variance"],
                   distortion=sh["noise_distortion"])
    normal = _bump(nt, micro.outputs["Fac"],
                   mill["micronormal_amplitude"],
                   scale_mm=mill["microparticle_scale_mm"],
                   law=sh["bump_distance_law"])
    nt.links.new(normal, b.inputs["Normal"])
    b.inputs["Specular IOR Level"].default_value = \
        sh["specular_ior_level"]
    b.inputs["Roughness"].default_value = round(
        sh["roughness_base"]
        - sh["roughness_smoothing_coeff"]
        * mill["surface_smoothing"], 4)
    b.inputs["Sheen Weight"].default_value = p["sheen_response"]["sheen"]
    if "Sheen Tint" in b.inputs:
        t = p["sheen_response"]["tint"]
        b.inputs["Sheen Tint"].default_value = (1.0 - t, 1.0 - t,
                                                1.0 - t, 1.0)
    _mottle_colour(nt, b, spec["display_rgb"], vec,
                   scale_mm=p["macrotexture"]["scale_mm"],
                   strength=p["macrotexture"]["strength"]
                   * sh["mottle_strength_factor"],
                   seed=spec["seed"], detail=sh["mottle_detail"],
                   seed_offset=sh["mottle_seed_offset"],
                   distortion=sh["noise_distortion"])


def _flake_field(nt, b, spec, vec, *, flakes):
    """SHIMMER and METALLIC: a per-cell flake census."""
    sh = spec["params"]["shader"]
    b.inputs["Specular IOR Level"].default_value = \
        sh["specular_ior_level"]
    v = _voronoi(nt, vec, scale_mm=flakes["flake_scale_mm"],
                 seed=spec["seed"])
    cell = _cell_random(nt, v)
    gate = _math(nt, "LESS_THAN", cell, flakes["flake_density"])
    metallic = _math(nt, "MULTIPLY", gate, flakes["metallic_response"])
    nt.links.new(metallic, b.inputs["Metallic"])
    # lit flakes are smoother than the powder between them
    flake_rough = (sh["flake_roughness_base"]
                   + sh["flake_roughness_metallic_coeff"]
                   * (1.0 - flakes["metallic_response"]))
    rough = _mix_scalar(nt, gate, spec["params"]["surface_roughness"],
                        flake_rough)
    nt.links.new(rough, b.inputs["Roughness"])
    jitter = (flakes["sparkle_intensity"]
              * sh["facet_jitter_per_sparkle"])
    nt.links.new(_facet_normal(nt, v, jitter), b.inputs["Normal"])
    _mottle_colour(nt, b, spec["display_rgb"], vec,
                   scale_mm=spec["params"]["macrotexture"]["scale_mm"],
                   strength=spec["params"]["macrotexture"]["strength"],
                   seed=spec["seed"], detail=sh["mottle_detail"],
                   seed_offset=sh["mottle_seed_offset"],
                   distortion=sh["noise_distortion"])


def _mix_scalar(nt, fac, a, b_val):
    inv = _math(nt, "SUBTRACT", 1.0, fac)
    return _math(nt, "ADD", _math(nt, "MULTIPLY", inv, a),
                 _math(nt, "MULTIPLY", fac, b_val))


def _glitter(nt, b, spec, vec):
    p = spec["params"]["particles"]
    sh = spec["params"]["shader"]
    b.inputs["Specular IOR Level"].default_value = \
        sh["specular_ior_level"]
    v = _voronoi(nt, vec, scale_mm=p["particle_size_mm"],
                 seed=spec["seed"],
                 distance=sh["voronoi_distance"])
    cell = _cell_random(nt, v)
    gate = _math(nt, "LESS_THAN", cell, p["coverage"])
    nt.links.new(_math(nt, "MULTIPLY", gate, p["reflectance"]),
                 b.inputs["Metallic"])
    rough = _mix_scalar(nt, gate, spec["params"]["surface_roughness"],
                        sh["particle_roughness"])
    nt.links.new(rough, b.inputs["Roughness"])
    jitter = (p["orientation_jitter_deg"]
              / sh["jitter_denominator_deg"])
    nt.links.new(_facet_normal(nt, v, jitter), b.inputs["Normal"])
    _mottle_colour(nt, b, spec["display_rgb"], vec,
                   scale_mm=spec["params"]["macrotexture"]["scale_mm"],
                   strength=spec["params"]["macrotexture"]["strength"],
                   seed=spec["seed"], detail=sh["mottle_detail"],
                   seed_offset=sh["mottle_seed_offset"],
                   distortion=sh["noise_distortion"])


def _baked(nt, b, spec, vec):
    p = spec["params"]
    sh = p["shader"]
    b.inputs["Specular IOR Level"].default_value = \
        sh["specular_ior_level"]
    crust = _noise(nt, vec, scale_mm=sh["crust_noise_scale_mm"],
                   seed=spec["seed"],
                   detail=sh["crust_noise_detail"],
                   distortion=sh["crust_distortion"])
    normal = _bump(nt, crust.outputs["Fac"],
                   p["crust"]["baked_microtexture_strength"],
                   scale_mm=sh["crust_noise_scale_mm"],
                   law=sh["bump_distance_law"])
    nt.links.new(normal, b.inputs["Normal"])
    b.inputs["Roughness"].default_value = sh["baked_roughness"]
    b.inputs["Coat Weight"].default_value = (p["crust"]["gloss"]
                                             * sh["coat_gloss_factor"])
    _mottle_colour(nt, b, spec["display_rgb"], vec,
                   scale_mm=p["macrotexture"]["scale_mm"],
                   strength=p["macrotexture"]["strength"],
                   seed=spec["seed"], detail=sh["mottle_detail"],
                   seed_offset=sh["mottle_seed_offset"],
                   distortion=sh["noise_distortion"])


def _derived_components(rgb, count, deriv):
    """C6 — chromatic component derivation. The pre-repair
    scalar (x0.55 / x1.35+0.05) preserved R:G:B exactly,
    producing a luminance marble (census L305, the marbling
    FAIL diagnosis). Per-channel asymmetric coefficients
    make the veins genuinely chromatic."""
    if deriv["form"] != "PER_CHANNEL_ASYMMETRIC_CHROMATIC":
        raise ValueError(f"undeclared derivation {deriv['form']!r}")
    dk = deriv["darker_rgb_coeffs"]
    lk = deriv["lighter_rgb_coeffs"]
    lo = deriv["lighter_rgb_offsets"]
    darker = [max(v * c, 0.0) for v, c in zip(rgb, dk)]
    lighter = [min(v * c + o, 1.0)
               for v, c, o in zip(rgb, lk, lo)]
    return [list(rgb), darker, lighter][:count]


def _marbled(nt, b, spec, vec):
    p = spec["params"]["marbling"]
    sh = spec["params"]["shader"]
    b.inputs["Specular IOR Level"].default_value = \
        sh["specular_ior_level"]
    mapping = _new(nt, "ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (
        0.0, 0.0, p["directional_bias_deg"] * 3.14159 / 180.0)
    nt.links.new(vec, mapping.inputs["Vector"])
    veins = _noise(nt, mapping.outputs["Vector"],
                   scale_mm=p["vein_scale_mm"], seed=spec["seed"],
                   detail=sh["vein_detail"],
                   distortion=sh["vein_distortion"])
    comps = _derived_components(spec["display_rgb"], p["components"],
                                sh["component_derivation"])
    r0 = p["mixing_ratio"][0]
    ramp = _new(nt, "ShaderNodeMapRange")
    ramp.interpolation_type = "SMOOTHSTEP"
    ramp.inputs["From Min"].default_value = max(
        r0 - sh["ramp_width_2comp"], 0.0)
    ramp.inputs["From Max"].default_value = min(
        r0 + sh["ramp_width_2comp"], 1.0)
    nt.links.new(veins.outputs["Fac"], ramp.inputs["Value"])
    colour = _mix_rgb(nt, ramp.outputs["Result"], comps[0], comps[1])
    if p["components"] == 3:
        veins2 = _noise(nt, mapping.outputs["Vector"],
                        scale_mm=p["vein_scale_mm"]
                        * sh["vein2_scale_factor"],
                        seed=spec["seed"] + sh["vein2_seed_offset"],
                        detail=sh["vein_detail"],
                        distortion=sh["vein_distortion"])
        r1 = p["mixing_ratio"][2]
        ramp2 = _new(nt, "ShaderNodeMapRange")
        ramp2.interpolation_type = "SMOOTHSTEP"
        ramp2.inputs["From Min"].default_value = (1.0 - r1
            - sh["ramp_width_3comp"])
        ramp2.inputs["From Max"].default_value = min(
            1.0 - r1 + sh["ramp_width_3comp"], 1.0)
        nt.links.new(veins2.outputs["Fac"], ramp2.inputs["Value"])
        colour = _mix_rgb(nt, ramp2.outputs["Result"], colour, comps[2])
    nt.links.new(colour, b.inputs["Base Color"])
    micro = _noise(nt, vec,
                   scale_mm=spec["params"]["microtexture"]["scale_mm"],
                   seed=spec["seed"] + sh["micro_seed_offset"],
                   detail=sh["micro_noise_detail"],
                   distortion=sh["noise_distortion"])
    nt.links.new(
        _bump(nt, micro.outputs["Fac"],
              spec["params"]["microtexture"]["strength"]
              * sh["microtexture_strength_factor"],
              scale_mm=spec["params"]["microtexture"]["scale_mm"],
              law=sh["bump_distance_law"]),
        b.inputs["Normal"])
    b.inputs["Roughness"].default_value = \
        spec["params"]["surface_roughness"]


def _pressed(nt, b, spec, vec):
    """§6 — compaction realized: a packed surface is smoother, flatter
    and finer than loose powder, and each of those is a compaction
    parameter, never an inherited constant."""
    p = spec["params"]
    sh = p["shader"]
    cpt = p["compaction"]
    b.inputs["Specular IOR Level"].default_value = \
        sh["specular_ior_level"]
    micro = _noise(nt, vec,
                   scale_mm=cpt["compression_texture_scale_mm"],
                   seed=spec["seed"],
                   detail=sh["micro_noise_detail"],
                   distortion=sh["noise_distortion"])
    normal = _bump(nt, micro.outputs["Fac"],
                   cpt["compression_texture_amplitude"],
                   scale_mm=cpt["compression_texture_scale_mm"],
                   law=sh["bump_distance_law"])
    nt.links.new(normal, b.inputs["Normal"])
    # the compaction ring lives in Generated (bounding-box) space so it
    # stays centred on any pan shape
    tc = _new(nt, "ShaderNodeTexCoord")
    cen = _new(nt, "ShaderNodeVectorMath")
    cen.operation = "SUBTRACT"
    nt.links.new(tc.outputs["Generated"], cen.inputs[0])
    cen.inputs[1].default_value = (0.5, 0.5, 0.5)
    flat = _new(nt, "ShaderNodeVectorMath")
    flat.operation = "MULTIPLY"
    nt.links.new(cen.outputs["Vector"], flat.inputs[0])
    flat.inputs[1].default_value = (2.0, 2.0, 0.0)
    length = _new(nt, "ShaderNodeVectorMath")
    length.operation = "LENGTH"
    nt.links.new(flat.outputs["Vector"], length.inputs[0])
    dist = _math(nt, "ABSOLUTE", _math(nt, "SUBTRACT",
                                       length.outputs["Value"],
                                       p["press"]["ring_radius_frac"]))
    ring = _math(nt, "EXPONENT",
                 _math(nt, "MULTIPLY",
                       _math(nt, "MULTIPLY", dist, dist),
                       sh["ring_gaussian_falloff"]))
    # compaction lowers the base roughness from the loose-powder value
    packed = p["surface_roughness"] * (
        1.0 - sh["packed_roughness_compaction_coeff"]
        * cpt["compaction_level"])
    rough = _math(nt, "SUBTRACT", packed,
                  _math(nt, "MULTIPLY", ring,
                        p["press"]["ring_strength"]))
    nt.links.new(rough, b.inputs["Roughness"])
    _mottle_colour(nt, b, spec["display_rgb"], vec,
                   scale_mm=p["macrotexture"]["scale_mm"],
                   strength=p["macrotexture"]["strength"]
                   * (1.0 - sh["mottle_flatness_coeff"]
                      * cpt["surface_flatness"]),
                   seed=spec["seed"], detail=sh["mottle_detail"],
                   seed_offset=sh["mottle_seed_offset"],
                   distortion=sh["noise_distortion"])


def _cream(nt, b, spec, vec):
    p = spec["params"]
    b.inputs["Roughness"].default_value = \
        p["continuity"]["soft_specular_roughness"]
    b.inputs["Base Color"].default_value = (*spec["display_rgb"], 1.0)
    # continuity IS the structure: no bump, no grain, no cells. A very
    # low-frequency swell keeps it organic without granularity.
    sh = p["shader"]
    b.inputs["Specular IOR Level"].default_value = \
        sh["specular_ior_level"]
    swell = _noise(nt, vec, scale_mm=sh["swell_scale_mm"],
                   seed=spec["seed"], detail=sh["swell_detail"],
                   distortion=sh["noise_distortion"])
    nt.links.new(_bump(nt, swell.outputs["Fac"],
                       sh["swell_amplitude"],
                       scale_mm=sh["swell_scale_mm"],
                       law=sh["bump_distance_law"]),
                 b.inputs["Normal"])


_BUILDERS = {
    "POWDER_MATTE": _matte,
    "POWDER_SATIN": _satin,
    "SHIMMER": lambda nt, b, s, v: _flake_field(
        nt, b, s, v, flakes=s["params"]["flakes"]),
    "POWDER_METALLIC": lambda nt, b, s, v: _flake_field(
        nt, b, s, v, flakes=s["params"]["flakes"]),
    "GLITTER": _glitter,
    "BAKED": _baked,
    "MARBLED": _marbled,
    "PRESSED_POWDER": _pressed,
    "CREAM": _cream,
}


def build(name, spec):
    """spec is PowderMaterialSpec.realize() — refuses unknown families."""
    family = spec["powder_family"]
    if family not in _BUILDERS:
        raise RuntimeError(f"no powder builder for family {family!r}")
    mat, nt, b = _base(f"POWDER_{family}_{name}", spec["display_rgb"])
    vec = _coords(nt, spec["seed"])
    _BUILDERS[family](nt, b, spec, vec)
    return mat
