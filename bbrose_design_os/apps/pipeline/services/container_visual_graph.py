"""Selected-concept identity + visual graph for container reconstruction
(Phase 2B-2, slice 1).

Two additive ``spec_sheet`` records, both DETERMINISTIC and derived with NO
provider call (vision extraction is forbidden — §14 golden hashes require
reproducibility):

    container_selected_variation/1.0                 the verified identity of
                                                     the exact approved image
    container_selected_concept_visual_graph/1.0      bounded visual
                                                     relationships of that
                                                     concept

Identity is resolved from the persisted record only — ``approved_image`` +
``reference_provenance`` + the ``gate1_reference_regeneration_prompts/1.0``
payload (reusing the target-agnostic ``selected_concept`` service). It FAILS
CLOSED with ``SELECTED_CONTAINER_VARIATION_IDENTITY_REQUIRED`` when the
approved image is missing/unpersisted, or (for a regenerated image) when its
structured record cannot be matched to the approved prompt — the broader
direction or first concept is never substituted (§2).

Every visual-graph field carries value / confidence / source / verification.
Fields come from three honest tiers, never from pixel guessing dressed as
fact:

* SELECTED_VARIATION_RECORD  — the prompt-verified structured variation
* SELECTED_VARIATION_PROMPT  — verbatim, deterministic prompt extraction
* LOCAL_IMAGE_ANALYSIS       — PIL/numpy on the approved render (INFERRED)

What needs vision (exact logo/name bounding boxes, front/back relationship,
wrap continuation) stays MISSING rather than being invented — that becomes an
UNMEASURED fidelity axis in slice 4, never an auto-pass.
"""
from __future__ import annotations

import hashlib
import json

from apps.pipeline.services.container_contract import (
    INFERRED,
    MISSING,
    VERIFIED,
)
from apps.pipeline.services.selected_concept import (
    extract_copy_lines,
    load_selected_variation,
    reconstruction_spec,
)

IDENTITY_SCHEMA = "container_selected_variation/1.0"
SCHEMA = "container_selected_concept_visual_graph/1.0"
SELECTED_VARIATION_IDENTITY_REQUIRED = "SELECTED_CONTAINER_VARIATION_IDENTITY_REQUIRED"

# --- field sources -----------------------------------------------------------
SRC_VARIATION_RECORD = "SELECTED_VARIATION_RECORD"
SRC_VARIATION_PROMPT = "SELECTED_VARIATION_PROMPT"
SRC_LOCAL_IMAGE = "LOCAL_IMAGE_ANALYSIS"
SRC_PROFILE = "CONFIRMED_CONTAINER_PROFILE"
SRC_UNKNOWN = "UNKNOWN"
#: §BH70(1), item 11 of the list the owner was sent: why a form drawn in plan has no cap colour on its concept record
PLAN_HAS_NO_CAP_AT_THE_TOP = ("a form drawn in plan is pictured from above: the top of its picture is background, not "
                              "a cap, so no cap colour is read there")

# fixed, deterministic confidences (never a random or time-varying value)
_C_VERIFIED = 1.0
_C_RECORD = 0.9
_C_PROMPT = 0.6
_C_LOCAL = 0.5
_C_NONE = 0.0

#: motif signature vocabulary → motif family (mirrors concept_fidelity)
_MOTIF_FAMILY_MAP = (
    (("particle", "constellation", "dot", "scatter", "powder", "speck"),
     "powder_constellation"),
    (("stripe", "ruled", "pinstripe", "line pattern"), "ruled_field"),
    (("liquid", "pour", "veil", "flow"), "liquid_veil"),
    (("contour", "topographic", "terrain"), "contour_terrain"),
    (("petal", "floral", "botanical", "rose", "flower"), "petal_scatter"),
    (("strata", "band", "block"), "strata_field"),
)
_FINISH_KEYWORDS = ("foil", "gloss", "matte", "metallic", "emboss", "deboss",
                    "pearlescent", "satin", "spot uv", "varnish")


class SelectedVariationIdentityError(ValueError):
    """Raised when the selected variation cannot be verified — the reconstruct
    wrapper turns this into the stable refusal code and returns to the gate."""
    code = SELECTED_VARIATION_IDENTITY_REQUIRED

    def __init__(self, reason: str = ""):
        msg = SELECTED_VARIATION_IDENTITY_REQUIRED
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
        self.reason = reason


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str)


def _hash(payload) -> str:
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()[:32]


def _sha_text(text: str) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()


def _vf(value, *, confidence, source, verification) -> dict:
    return {"value": value, "confidence": confidence, "source": source,
            "verification": verification}


def _iso(dt) -> str:
    try:
        return dt.isoformat()
    except AttributeError:
        return ""


# --- selected-variation identity (§2) ---------------------------------------

def resolve_selected_variation_identity(task, output) -> dict:
    """The verified identity of the EXACT approved Gate-1 image + its
    structured variation record (or None for a first-pass concept). Raises
    SelectedVariationIdentityError (→ fail closed) when it cannot be verified.

    Returns {"identity": {...}, "structured": dict|None}.
    """
    image = getattr(output, "approved_image", None)
    if image is None:
        raise SelectedVariationIdentityError("no approved image on the output")
    if not (image.prompt_used or "").strip():
        raise SelectedVariationIdentityError(
            "the approved image has no persisted prompt to verify against")

    variation = load_selected_variation(task, image)
    if isinstance(variation, dict) and variation.get("verified") is False:
        # the identity exists but its record cannot be matched — never fall
        # back to the direction or the first concept
        raise SelectedVariationIdentityError(
            variation.get("reason", "the variation record did not verify"))
    structured = variation if (variation and variation.get("verified")) else None

    decision = (task.gate_decisions.filter(gate="gate_1", decision="approve")
                .order_by("-decided_at").first())
    reg_job_id = None
    if structured is not None:
        from apps.pipeline.models import Gate1RegenerationJob
        job = (Gate1RegenerationJob.objects
               .filter(task=task, status=Gate1RegenerationJob.STATUS_COMPLETED)
               .order_by("-id").first())
        reg_job_id = job.id if job else None

    prov = image.reference_provenance or {}
    identity = {
        "schema_version": IDENTITY_SCHEMA,
        "task_id": task.id,
        "direction_name": image.direction_name or "",
        "generated_image_id": image.id,
        "variation_number": image.variation_number,
        "variation_id": prov.get("variation_identity", "") or "",
        "variation_title": (structured or {}).get("title", "") if structured else "",
        "regeneration_job_id": reg_job_id,
        "approved_prompt_hash": _sha_text(image.prompt_used),
        "selected_at": _iso(decision.decided_at) if decision else _iso(
            getattr(image, "created_at", None)),
        "selected_by": (decision.decided_by.username
                        if decision and decision.decided_by else ""),
        "structured_record_present": structured is not None,
        "verified": True,
    }
    # identity hash excludes volatile who/when — a re-run reads the same hash
    identity["source_hash"] = _hash({
        k: identity[k] for k in (
            "schema_version", "task_id", "generated_image_id",
            "variation_id", "approved_prompt_hash",
            "structured_record_present")})
    return {"identity": identity, "structured": structured}


# --- local (no-provider) image analysis -------------------------------------

def _motif_family(motif_signature: str) -> str | None:
    text = (motif_signature or "").lower()
    for keywords, family in _MOTIF_FAMILY_MAP:
        if any(k in text for k in keywords):
            return family
    return None


def analyze_image(path: str | None) -> dict:
    """Deterministic local descriptors of the approved render — palette,
    colour-area proportions, whitespace, motif density + centroid. No
    provider, no network. Degrades to {} on any error (the field then stays
    MISSING). Same image → same numbers (golden-hash safe)."""
    if not path:
        return {}
    try:
        import numpy as np
        from PIL import Image

        with Image.open(path) as im:
            rgb = im.convert("RGB")
            rgb.thumbnail((96, 96))
            arr = np.asarray(rgb, dtype=np.float64)
        h, w = arr.shape[0], arr.shape[1]
        total = max(1, h * w)
        flat = arr.reshape(-1, 3)
        # dominant colour = median (robust to specks)
        med = np.median(flat, axis=0)
        dominant = "#{:02X}{:02X}{:02X}".format(
            int(round(med[0])), int(round(med[1])), int(round(med[2])))
        # colour-area proportions: coarse 3-bit-per-channel buckets
        buckets = (flat // 64).astype(int)
        keys = buckets[:, 0] * 100 + buckets[:, 1] * 10 + buckets[:, 2]
        uniq, counts = np.unique(keys, return_counts=True)
        order = np.argsort(-counts)[:5]
        proportions = []
        for idx in order:
            b = int(uniq[idx])
            r, g, bl = (b // 100) % 10, (b // 10) % 10, b % 10
            hexv = "#{:02X}{:02X}{:02X}".format(
                min(255, r * 64 + 32), min(255, g * 64 + 32),
                min(255, bl * 64 + 32))
            proportions.append([hexv, round(float(counts[idx]) / total, 4)])
        # whitespace = fraction close to the dominant (quiet field)
        dist = np.sqrt(((flat - med) ** 2).sum(axis=1))
        whitespace = round(float((dist < 40).sum()) / total, 4)
        # motif density = fraction of "busy" pixels (local luminance gradient)
        lum = arr.mean(axis=2)
        gy = np.abs(np.diff(lum, axis=0))
        gx = np.abs(np.diff(lum, axis=1))
        busy_y = gy > 18
        busy_x = gx > 18
        busy_count = int(busy_y.sum() + busy_x.sum())
        density = round(busy_count / (2.0 * total), 4)
        # motif centroid (normalised) of the busy pixels, else image centre
        ys, xs = np.nonzero(busy_y)
        if len(xs):
            cx = round(float(xs.mean()) / max(1, w - 1), 3)
            cy = round(float(ys.mean()) / max(1, h - 1), 3)
        else:
            cx, cy = 0.5, 0.5
        # top vs. bottom dominant (cap-vs-body coordination hint)
        top = np.median(arr[: max(1, h // 4)].reshape(-1, 3), axis=0)
        top_hex = "#{:02X}{:02X}{:02X}".format(
            int(round(top[0])), int(round(top[1])), int(round(top[2])))
        # 2B-3V-CORR-3 §4: droplet estimate = connected bright-blob count on
        # the busy mask (LOW-confidence relationship, never a production fact)
        busy = np.zeros((h, w), dtype=bool)
        busy[: h - 1, :] |= busy_y
        busy[:, : w - 1] |= busy_x
        labels = np.zeros((h, w), dtype=int)
        blob_sizes: list[int] = []
        blob_cys: list[float] = []
        nxt = 0
        for yy in range(h):
            for xx in range(w):
                if busy[yy, xx] and labels[yy, xx] == 0:
                    nxt += 1
                    stack = [(yy, xx)]
                    size, cy_sum = 0, 0.0
                    while stack:
                        py_, px_ = stack.pop()
                        if not (0 <= py_ < h and 0 <= px_ < w) \
                                or not busy[py_, px_] or labels[py_, px_]:
                            continue
                        labels[py_, px_] = nxt
                        size += 1
                        cy_sum += py_
                        stack.extend([(py_ + 1, px_), (py_ - 1, px_),
                                      (py_, px_ + 1), (py_, px_ - 1)])
                    if size >= 3:                     # ignore speck noise
                        blob_sizes.append(size)
                        blob_cys.append(cy_sum / size / max(1, h - 1))
        upper = sum(1 for c in blob_cys if c < 0.5)
        lower = max(1, len(blob_cys) - upper)
        movement = ("vertical_sparse_to_dense_upward" if upper > lower
                    else "vertical_dense_to_sparse_downward"
                    if lower > upper * 1.5 else "distributed")
        sizes_sorted = sorted(blob_sizes)
        size_classes = 0
        if sizes_sorted:
            small = sum(1 for s_ in sizes_sorted if s_ < 8)
            mid = sum(1 for s_ in sizes_sorted if 8 <= s_ < 30)
            large = sum(1 for s_ in sizes_sorted if s_ >= 30)
            size_classes = sum(1 for n in (small, mid, large) if n > 0)
        return {
            "dominant_hex": dominant,
            "color_area_proportions": proportions,
            "whitespace_fraction": whitespace,
            "motif_density": density,
            "motif_centroid": {"x": cx, "y": cy},
            "top_region_hex": top_hex,
            "droplet_count_estimate": len(blob_sizes),
            "droplet_size_classes": size_classes,
            "movement_direction": movement,
            "vertical_density_ratio": round(upper / lower, 3),
        }
    except Exception:  # noqa: BLE001 — analysis is best-effort, never fatal
        return {}


# --- visual graph (§3) -------------------------------------------------------

def build_visual_graph(task, output, profile_record: dict | None,
                       structured: dict | None, image_path: str | None) -> dict:
    """Assemble container_selected_concept_visual_graph/1.0. Deterministic:
    same approved image + same structured record → identical fields + hash."""
    profile_record = profile_record or {}
    image = getattr(output, "approved_image", None)
    prompt = (getattr(image, "prompt_used", "") or "")
    product_name = (output.spec_sheet or {}).get("product_name", "") \
        if getattr(output, "spec_sheet", None) else ""

    spec = reconstruction_spec(structured or {}, product_name=product_name) \
        if structured else {}
    copy = extract_copy_lines({"prompt": prompt}, product_name)
    local = analyze_image(image_path)

    fields: dict = {}

    # container silhouette — from the confirmed profile (concept-level, INFERRED)
    archetype = profile_record.get("archetype") or ""
    fields["container_silhouette"] = _vf(
        archetype or None, confidence=_C_LOCAL if archetype else _C_NONE,
        source=SRC_PROFILE if archetype else SRC_UNKNOWN,
        verification=INFERRED if archetype else MISSING)

    # §BH70(1), item 11 of the list the owner was sent: a form drawn in plan — a compact — is pictured from above; the
    # concept directive asks it so since 5f6b730, and this record said it faced front and read its cap from the top
    # quarter of the picture, where there is only background
    from apps.pipeline.targets.container import archetypes as _declared
    in_plan = _declared.is_known(archetype) and _declared.drawn_as_of(archetype) == _declared.PLAN

    # front orientation — the concept directive forces an upright front packshot; a form in plan, seen from above
    fields["front_orientation"] = _vf(
        ("seen_from_above" if in_plan else "front_facing") if prompt else None,
        confidence=_C_PROMPT if prompt else _C_NONE,
        source=SRC_VARIATION_PROMPT if prompt else SRC_UNKNOWN,
        verification=INFERRED if prompt else MISSING)

    # logo / product-name zones — VERIFIED only from the structured record
    def _zone(field_key):
        val = spec.get(field_key)
        if val:
            return _vf(val, confidence=_C_RECORD, source=SRC_VARIATION_RECORD,
                       verification=VERIFIED)
        return _vf(None, confidence=_C_NONE, source=SRC_UNKNOWN,
                   verification=MISSING)

    fields["logo_zone"] = _zone("logo_zone")
    fields["product_name_zone"] = _zone("product_name_zone")

    # supporting copy — verbatim from the verified approved prompt
    supporting = list(copy.get("secondary") or [])
    fields["supporting_copy_zones"] = _vf(
        supporting or None,
        confidence=_C_PROMPT if supporting else _C_NONE,
        source=SRC_VARIATION_PROMPT if supporting else SRC_UNKNOWN,
        verification=VERIFIED if supporting else MISSING)
    fields["vertical_copy"] = _vf(
        copy.get("vertical"),
        confidence=_C_PROMPT if copy.get("vertical") else _C_NONE,
        source=SRC_VARIATION_PROMPT if copy.get("vertical") else SRC_UNKNOWN,
        verification=VERIFIED if copy.get("vertical") else MISSING)

    # motif family — from the structured motif signature
    family = _motif_family(spec.get("motif_signature", "")) if spec else None
    fields["motif_family"] = _vf(
        family, confidence=_C_RECORD if family else _C_NONE,
        source=SRC_VARIATION_RECORD if family else SRC_UNKNOWN,
        verification=VERIFIED if family else MISSING)

    # 2B-3V-CORR-3 §4: droplet-constellation relationships measured from the
    # ACTUAL selected image — LOW/MEDIUM-confidence visual RELATIONSHIPS
    # (each with tolerance), never exact production facts.
    for key, tol in (("droplet_count_estimate", "±40%"),
                     ("droplet_size_classes", "±1 class"),
                     ("movement_direction", "categorical"),
                     ("vertical_density_ratio", "±0.5")):
        val = local.get(key)
        f = _vf(val, confidence="LOW" if val is not None else _C_NONE,
                source=SRC_LOCAL_IMAGE if val is not None else SRC_UNKNOWN,
                verification=INFERRED if val is not None else MISSING)
        f["tolerance"] = tol
        fields[key] = f

    # motif region / centroid / density — local, INFERRED
    for key, sub in (("motif_centroid", "motif_centroid"),
                     ("motif_density", "motif_density")):
        val = local.get(sub)
        fields[key] = _vf(
            val, confidence=_C_LOCAL if val is not None else _C_NONE,
            source=SRC_LOCAL_IMAGE if val is not None else SRC_UNKNOWN,
            verification=INFERRED if val is not None else MISSING)

    # decoration coverage — structured pct (VERIFIED) else local density proxy
    cov = spec.get("decorative_coverage_pct") if spec else None
    if cov is not None:
        fields["decoration_coverage"] = _vf(
            cov, confidence=_C_RECORD, source=SRC_VARIATION_RECORD,
            verification=VERIFIED)
    else:
        d = local.get("motif_density")
        fields["decoration_coverage"] = _vf(
            d, confidence=_C_LOCAL if d is not None else _C_NONE,
            source=SRC_LOCAL_IMAGE if d is not None else SRC_UNKNOWN,
            verification=INFERRED if d is not None else MISSING)

    # colour relationships — local, INFERRED
    props = local.get("color_area_proportions")
    fields["color_area_proportions"] = _vf(
        props, confidence=_C_LOCAL if props else _C_NONE,
        source=SRC_LOCAL_IMAGE if props else SRC_UNKNOWN,
        verification=INFERRED if props else MISSING)
    fields["body_base_color"] = _vf(
        local.get("dominant_hex"),
        confidence=_C_LOCAL if local.get("dominant_hex") else _C_NONE,
        source=SRC_LOCAL_IMAGE if local.get("dominant_hex") else SRC_UNKNOWN,
        verification=INFERRED if local.get("dominant_hex") else MISSING)
    coord = None
    if local.get("dominant_hex") and local.get("top_region_hex") and not in_plan:
        coord = {"body": local["dominant_hex"], "cap_region": local["top_region_hex"]}
    fields["body_cap_color_coordination"] = _vf(
        coord, confidence=_C_LOCAL if coord else _C_NONE,
        source=SRC_LOCAL_IMAGE if coord else SRC_UNKNOWN,
        verification=INFERRED if coord else MISSING)
    if in_plan:
        fields["body_cap_color_coordination"]["note"] = PLAN_HAS_NO_CAP_AT_THE_TOP
    fields["whitespace_distribution"] = _vf(
        local.get("whitespace_fraction"),
        confidence=_C_LOCAL if local.get("whitespace_fraction") is not None else _C_NONE,
        source=SRC_LOCAL_IMAGE if local.get("whitespace_fraction") is not None else SRC_UNKNOWN,
        verification=INFERRED if local.get("whitespace_fraction") is not None else MISSING)

    # finish intent — verbatim prompt keywords
    finishes = [k for k in _FINISH_KEYWORDS if k in prompt.lower()]
    fields["finish_intent"] = _vf(
        finishes or None, confidence=_C_PROMPT if finishes else _C_NONE,
        source=SRC_VARIATION_PROMPT if finishes else SRC_UNKNOWN,
        verification=INFERRED if finishes else MISSING)

    # relationships that genuinely need vision — honestly MISSING (never faked)
    for key in ("dominant_alignment_axes", "front_back_visual_relationship",
                "wrap_continuation_direction", "label_edge_relationship"):
        fields[key] = _vf(None, confidence=_C_NONE, source=SRC_UNKNOWN,
                          verification=MISSING)

    graph = {
        "schema_version": SCHEMA,
        "structured_record_present": structured is not None,
        "fields": fields,
    }
    graph["visual_graph_hash"] = visual_graph_hash(graph)
    return graph


def visual_graph_hash(graph: dict) -> str:
    """Deterministic identity of the visual graph (no timestamps present)."""
    core = {"schema_version": graph.get("schema_version"),
            "structured_record_present": graph.get("structured_record_present"),
            "fields": {k: {"value": v.get("value"), "source": v.get("source"),
                           "verification": v.get("verification"),
                           "confidence": v.get("confidence")}
                       for k, v in (graph.get("fields") or {}).items()}}
    return _hash(core)


__all__ = [
    "IDENTITY_SCHEMA", "SCHEMA", "SELECTED_VARIATION_IDENTITY_REQUIRED",
    "SelectedVariationIdentityError", "resolve_selected_variation_identity",
    "build_visual_graph", "visual_graph_hash", "analyze_image",
    "SRC_VARIATION_RECORD", "SRC_VARIATION_PROMPT", "SRC_LOCAL_IMAGE",
    "SRC_PROFILE", "SRC_UNKNOWN",
]
