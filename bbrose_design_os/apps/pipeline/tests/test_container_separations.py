"""Phase 2B-3B §6-§8/§11-§14 — production separations + swatch/spot contract.

Separations are a data manifest with visibility defaults: PROCESS_ARTWORK
visible, finish/technical separations hidden (never opaque fills over the
design). Spot swatches are technical placeholders pending manufacturer review;
names are unique. White underbase is keyed off CONFIRMED transparency, never
assumed. Label/sleeve technical geometry is deterministic; hashing invalidates
on change.
"""
from __future__ import annotations

from apps.ire import container_production_method as pm
from apps.ire import container_separations as sep
from apps.ire.compose_container import compose_container_graph
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)


def _build(archetype="bottle", zone_overrides=None, profile_overrides=None):
    prof = cc.build_inferred_profile(archetype, estimates={
        "body_width_mm": 40.0, "body_height_mm": 110.0,
        "cap_width_mm": 20.0, "cap_height_mm": 13.0})
    if profile_overrides:
        prof["fields"].update(profile_overrides)
    zones = cc.propose_zones(prof)
    if zone_overrides:
        zone_overrides(zones)
    bb = build_backbone(ContainerProfile(archetype=archetype, width_mm=40,
                                         height_mm=110))
    doc = compose_container_graph(bb, product_name="Rose Nectar",
                                  name_lines=["Rose Nectar"], zones=zones,
                                  native=True)
    methods = pm.build_production_methods(zones, prof)
    return sep.build_separations(methods, doc, zones, prof), methods, prof, zones


def test_process_artwork_visible_finishes_hidden():
    rec, *_ = _build()
    seps = {s["name"]: s for s in rec["separations"]}
    assert seps["PROCESS_ARTWORK"]["visibility_default"] == "visible"
    assert seps["PROCESS_ARTWORK"]["classification"] == sep.PROCESS
    # every non-process separation is hidden by default (§7)
    for s in rec["separations"]:
        if s["name"] != "PROCESS_ARTWORK":
            assert s["visibility_default"] == "hidden"


def test_swatch_names_unique_and_spots_are_placeholders():
    rec, *_ = _build()
    names = [s["name"] for s in rec["swatches"]]
    assert len(names) == len(set(names))          # no duplicates
    for s in rec["swatches"]:
        if s["classification"] == sep.SPOT:
            assert s["value"] == "TECHNICAL_PLACEHOLDER"
            assert s["manufacturer_review"] is True


def test_screen_and_cap_methods_yield_ink_separations():
    rec, *_ = _build()
    names = {s["name"] for s in rec["separations"]}
    assert "SCREEN_INK_1" in names                # bottle front = screen print
    assert "PAD_PRINT_INK_1" in names             # cap-top = cap print


def test_white_underbase_requires_confirmed_transparency():
    # unknown transparency (the default) → REVIEW_REQUIRED, not generated
    rec, *_ = _build()
    ub = rec["white_underbase"]
    assert ub["state"] == "REVIEW_REQUIRED"
    assert ub["code"] == "CONTAINER_WHITE_UNDERBASE_REQUIRED"
    names = {s["name"] for s in rec["separations"]}
    assert "WHITE_UNDERBASE" not in names

    # confirmed transparent → generated as a hidden spot separation
    rec2, *_ = _build(profile_overrides={
        "body_transparency": {"value": "transparent", "verification": "VERIFIED"}})
    assert rec2["white_underbase"]["state"] == "GENERATED"
    ub_sep = next(s for s in rec2["separations"] if s["name"] == "WHITE_UNDERBASE")
    assert ub_sep["visibility_default"] == "hidden"
    assert ub_sep["classification"] == sep.SPOT


def test_label_and_sleeve_technical_geometry():
    def _to_wrap_label(zones):
        for z in zones:
            if z["parent_surface"] == "BODY_FRONT":
                z["permitted_techniques"] = ["wrap_label"]
    rec, *_ = _build(zone_overrides=_to_wrap_label)
    names = {s["name"] for s in rec["separations"]}
    assert {"LABEL_CUT", "LABEL_BLEED", "LABEL_SAFE"} <= names
    cut = next(s for s in rec["separations"] if s["name"] == "LABEL_CUT")
    assert cut["classification"] == sep.TECHNICAL
    assert cut["geometry"]["confirmed_cutline"] is False    # not auto-confirmed

    def _to_sleeve(zones):
        for z in zones:
            if z["parent_surface"] == "BODY_FRONT":
                z["permitted_techniques"] = ["shrink_sleeve"]
    rec2, *_ = _build(zone_overrides=_to_sleeve)
    seam = next(s for s in rec2["separations"] if s["name"] == "SHRINK_SLEEVE_SEAM")
    assert "DISTORTION_REVIEW_REQUIRED" in seam["geometry"]["distortion_review"]


def test_combined_hash_invalidates_on_change():
    rec, methods, prof, zones = _build()
    h1 = sep.combined_production_hash(methods, rec)
    # change a method's authority → combined hash must change
    methods["methods"][0]["authority_state"] = pm.VERIFIED_MANUFACTURER_CAPABILITY
    methods["method_set_hash"] = "different"
    h2 = sep.combined_production_hash(methods, rec)
    assert h1 != h2
