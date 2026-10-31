"""Phase 2B-2A slice 1 — container_motif_spec/1.0 + native motif library.

The motif is authored from the SELECTED variation and bound to the existing
closed design-language engine. The 12 mandate families collapse onto the
supported recipes and that collapse is recorded (requested_family vs
rendered_via); an unrebuildable motif fails closed with
VECTOR_RECONSTRUCTION_REVIEW_REQUIRED rather than being traced or swapped.
"""
from __future__ import annotations

from apps.ire import container_motif as cm
from apps.pipeline.services import container_contract as cc


def _zones():
    return cc.propose_zones(cc.build_inferred_profile("bottle"))


def _vg(centroid=None, density=None):
    fields = {}
    if centroid is not None:
        fields["motif_centroid"] = {"value": centroid, "verification": cc.INFERRED}
    if density is not None:
        fields["motif_density"] = {"value": density, "verification": cc.INFERRED}
    return {"schema_version": cm.SCHEMA, "fields": fields}


def test_classify_family_matches_signature():
    assert cm.classify_family("scattered powder constellation") == "POWDER_CONSTELLATION"
    assert cm.classify_family("soft botanical leaf line art") in (
        "BOTANICAL_LINE_ART", "SOFT_PETALS", "FLORAL_ABSTRACT")
    assert cm.classify_family("") is None


def test_no_structured_motif_is_capability_none():
    spec = cm.build_motif_spec(None, _vg(), _zones(), None)
    assert spec["reconstruction_capability"] == cm.CAP_NONE
    assert spec["requested_family"] is None
    assert spec["motif_hash"]


def test_supported_motif_records_family_and_render():
    structured = {"verified": True, "variation_id": "v1",
                  "motif_signature": "scattered powder constellation",
                  "decorative_coverage_pct": 18}
    spec = cm.build_motif_spec(structured, _vg(centroid={"x": 0.6, "y": 0.6},
                                               density=0.2), _zones(), None)
    assert spec["reconstruction_capability"] == cm.CAP_SUPPORTED
    assert spec["requested_family"] == "POWDER_CONSTELLATION"
    assert spec["rendered_via"] == "powder_constellation"
    assert spec["source_identity"] == "v1"
    # motif coverage came from the VERIFIED record
    assert spec["motif_coverage"]["verification"] == cc.VERIFIED
    # a real language is bound for rendering
    assert cm.language_for_spec(spec) is not None


def test_approximate_family_is_flagged():
    structured = {"verified": True, "variation_id": "v2",
                  "motif_signature": "delicate botanical leaf line-art"}
    spec = cm.build_motif_spec(structured, _vg(), _zones(), None)
    assert spec["reconstruction_capability"] == cm.CAP_SUPPORTED
    assert spec["requested_family"] == "BOTANICAL_LINE_ART"
    assert spec["rendered_via"] == "petal_scatter"       # nearest supported
    assert spec["rendered_via_is_approximate"] is True   # recorded honestly


def test_unrebuildable_motif_fails_closed():
    # a signature scoring < the keyword floor against EVERY language
    structured = {"verified": True, "variation_id": "v3",
                  "motif_signature": "iridescent prism facets"}
    spec = cm.build_motif_spec(structured, _vg(), _zones(), None)
    assert spec["reconstruction_capability"] == cm.CAP_REVIEW_REQUIRED
    assert spec["review_code"] == "VECTOR_RECONSTRUCTION_REVIEW_REQUIRED"
    assert spec["rendered_via"] is None
    assert cm.language_for_spec(spec) is None             # nothing to render


def test_target_surfaces_are_confirmed_body_zones():
    zones = _zones()
    structured = {"verified": True, "motif_signature": "powder constellation"}
    spec = cm.build_motif_spec(structured, _vg(), zones, None)
    # bottle proposals put print zones on BODY_FRONT / BODY_BACK (+ a cap zone)
    assert "BODY_FRONT" in spec["target_surfaces"]
    assert "CAP_TOP" not in spec["target_surfaces"]       # cap is not a motif field
    assert spec["target_zones"]


def test_motif_hash_is_deterministic():
    structured = {"verified": True, "variation_id": "v1",
                  "motif_signature": "powder constellation"}
    a = cm.build_motif_spec(structured, _vg(), _zones(), None)["motif_hash"]
    b = cm.build_motif_spec(structured, _vg(), _zones(), None)["motif_hash"]
    assert a == b and a


# ---------------------------------------------------------------------------------------------------------------
# §BH65(c) — THE ONE CONTRACT, motif side. FOUR classifiers name motif families (this module's, the planner's own
# direction_signature, the visual graph's analysis map, and the design languages' own keywords); every name any of
# them can emit is declared by the contract and routes to something that exists, and the composing classifier's
# routing IS the contract's — the same object, so the two cannot drift.
# ---------------------------------------------------------------------------------------------------------------


def test_the_composing_classifier_routes_through_the_contract_itself():
    from apps.ire import composer_vocabulary as V
    assert cm._FAMILY_TO_LANGUAGE is V.FAMILY_TO_LANGUAGE
    assert cm._APPROXIMATE_FAMILIES is V.APPROXIMATE_FAMILIES
    assert set(cm.FAMILIES) == set(V.FAMILY_TO_LANGUAGE)
    assert {family for family, _ in cm._FAMILY_KEYWORDS} == set(cm.FAMILIES)


def test_every_family_any_classifier_can_emit_is_declared_and_routes_to_a_real_language():
    from apps.ire import composer_vocabulary as V
    from apps.ire.design_language import _LANGUAGES
    from apps.pipeline.direction_signature import MOTIF_FAMILIES
    from apps.pipeline.services.container_visual_graph import _MOTIF_FAMILY_MAP
    emitted = set(cm.FAMILIES) | {name for name, _ in MOTIF_FAMILIES}
    assert emitted == set(V.families())
    for family in emitted:
        status, language, how = V.family_status(family)
        assert status != V.REFUSED and how, family
        assert language is None or language in _LANGUAGES, (family, language)
    # the visual graph's analysis map names LANGUAGES, not families — each must be one that exists
    assert {lang for _, lang in _MOTIF_FAMILY_MAP} <= set(_LANGUAGES)
    # a name no classifier emits is refused by name, never read as drawn
    assert V.family_status("NOT_A_FAMILY")[0] == V.REFUSED


def test_the_families_with_no_language_are_the_planners_three():
    """At (c)1 the planner reasoned in three families nothing could draw — LINEAR_ENGRAVED, PATTERN_REPEAT and
    GEOMETRIC_HALO — named so (c) knew what it owed. §BH65(c)4 paid it: each has a language, and none is left."""
    from apps.ire import composer_vocabulary as V
    unrouted = {f for f in V.families() if V.family_status(f)[1] is None and f != "NONE_MATERIAL"}
    assert unrouted == set()
    assert {f: V.family_status(f)[1] for f in ("LINEAR_ENGRAVED", "PATTERN_REPEAT", "GEOMETRIC_HALO")} == {
        "LINEAR_ENGRAVED": "engraved_field", "PATTERN_REPEAT": "pattern_repeat", "GEOMETRIC_HALO": "halo_rings"}


def test_the_visual_graph_finish_keywords_are_declared_finish_words():
    from apps.ire import composer_vocabulary as V
    from apps.pipeline.services.container_visual_graph import _FINISH_KEYWORDS
    for word in _FINISH_KEYWORDS:
        keys = V.scan(word, strip_negation=False)
        assert keys and all(V.TERM_BY_KEY[k].axis == "finish" for k in keys), (word, keys)


#: task 89's own finish sentence (A_PETAL_WINDOW, read-only 2026-09-23), verbatim
_TASK_89_FINISHES = ("Matte soft-touch laminate ground; rose-gold hot-stamp foil on petal outlines, window rule, "
                     "circumference rule ring and BBROSE wordmark; spot gloss UV over the cartouche interior; gloss "
                     "lacquer on side band")


def test_the_finish_slot_is_filled_from_the_concepts_own_sentence():
    """§BH65(c)2. The motif spec was given a slot for the concept's finishes in 2B-2A and it was ALWAYS {} — measured
    on tasks 84 and 89 at (c)1. It is filled now, clause by clause, each finish read through the ONE contract."""
    structured = {"verified": True, "variation_id": "A_PETAL_WINDOW",
                  "motif_signature": "seven petal-droplets in a radial cluster inside the window",
                  "finish_signature": _TASK_89_FINISHES}
    fa = cm.build_motif_spec(structured, _vg(), _zones(), None)["finish_assignments"]
    assert fa["state"] == "READ"
    assert [(c["finishes"], c["targets"]) for c in fa["clauses"]] == [
        ([{"kind": "soft_touch", "plate": "SOFT_TOUCH"}], ["ground"]),
        ([{"kind": "foil", "plate": "FOIL_ROSE_GOLD"}], ["motif", "ring", "window", "lockup"]),
        ([{"kind": "spot_uv", "plate": "SPOT_UV"}], ["window_interior"]),
        ([{"kind": "gloss_varnish", "plate": "VARNISH_GLOSS"}], ["band"]),
    ]


def test_no_finish_sentence_is_said_and_a_finish_with_no_target_floods_the_ground():
    from apps.ire import container_finishes as F
    assert F.assignments(None)["state"] == "NO_FINISH_SIGNATURE"
    assert cm.build_motif_spec(None, _vg(), _zones(), None)["finish_assignments"]["state"] == "NO_FINISH_SIGNATURE"
    clause = F.assignments("overall satin varnish")["clauses"][0]
    assert clause["targets"] == ["ground"] and clause["target_defaulted"] is False
    clause = F.assignments("a spot UV finish")["clauses"][0]
    assert clause["targets"] == ["ground"] and clause["target_defaulted"] is True
    # a negated finish is not asked for
    assert F.assignments("no foil anywhere")["clauses"] == []



def test_a_routed_family_is_drawn_on_the_front_from_c3_and_an_approximate_one_says_so():
    """§BH65(c)3: at (c)1 every routed family was TEACHING — the front drew the §BB4 divider in its place."""
    from apps.ire import composer_vocabulary as V
    assert V.family_status("DEWDROP_CONSTELLATION")[:2] == (V.DRAWN, "dewdrop_constellation")
    assert V.family_status("RADIANCE_LINES")[:2] == (V.APPROXIMATED, "contour_terrain")
    assert V.family_status("LINEAR_ENGRAVED")[:2] == (V.DRAWN, "engraved_field")   # §BH65(c)4 routed it



def test_the_composing_classifier_names_an_engraving_and_a_halo_and_draws_them_as_themselves():
    """§BH65(c)4: the composer's own classifier had no family for an engraving or a halo — "fine engraved guilloche
    linework" read as a ruled field, "a halo of concentric rings" as radiance lines. Each has its family and its
    language now, and MICRO_PATTERN is drawn as a pattern repeat rather than approximated by ruled lines."""
    for sig, family, language in (("fine engraved guilloche linework", "ENGRAVED_LINEWORK", "engraved_field"),
                                  ("a soft halo of concentric rings", "HALO_RINGS", "halo_rings"),
                                  ("a micro allover texture", "MICRO_PATTERN", "pattern_repeat")):
        spec = cm.build_motif_spec({"verified": True, "variation_id": "v", "motif_signature": sig}, _vg(),
                                   _zones(), None)
        assert (spec["requested_family"], spec["rendered_via"]) == (family, language), sig
        assert spec["reconstruction_capability"] == cm.CAP_SUPPORTED
        assert spec.get("rendered_via_is_approximate") in (False, None)


# --- §BH67(b)1: THE MOTIF IS THE FAMILY THE CONCEPT NAMED ---------------------------------------------------
#: EVERY Gate-1 variation record on record (21; the verified record each approved image's provenance names, read-only
#: 2026-09-24), its motif, title and composition words verbatim, with the family it must read. The five petal windows
#: read DEWDROP_CONSTELLATION until (b)1 — "drop" inside "teardrop" and "droplet" — and read SOFT_PETALS now; the
#: other sixteen read exactly as they did.
_RECORDED_VARIATIONS = {
    '50_A_EDITORIAL_PANEL': ('Repeating miniature diamond-lozenge micro-pattern inside the blush panel; three rose-gold circular powder-dot accents at panel terminus',
        'Editorial Asymmetric Panel',
        'Asymmetric left vertical blush panel with micro-pattern alongside oversized centered condensed stacked type; BBROSE upper-right; Spanish copy lower anchored to panel edge',
        'POWDER_CONSTELLATION'),
    '50_B_LAYERED_TYPE_FIELD': ('Eight-to-twelve fine straight radiance hairlines tapering from a mid-left focal point; one small open rose-gold rectangle accent lower right',
        'Layered Type Field',
        'Sky-blue upper tonal block over ivory lower field with clean horizon break; centered BBROSE crown; layered two-color stacked type at panel center; left peach vertical band; radiance hairlines behind type; bilingual cluster lower-left',
        'RADIANCE_LINES'),
    '50_C_POWDER_CONSTELLATION': ('Forty-to-sixty vector powder particles — mixed fine dots, slim ellipses and cross-tick hairlines in rose-gold — forming a dispersing constellation from lower-right corner toward mid-panel and continuing onto the side panel',
        'Powder Constellation',
        'Left-asymmetric editorial type hierarchy with BBROSE upper-left anchored by partial open rectangle frame; powder-particle constellation massing at lower-right dispersing diagonally; vertical Spanish copy on right edge',
        'POWDER_CONSTELLATION'),
    '51_A_PETAL_WINDOW': ('Seven to nine closed Bézier elongated teardrop petal-drop forms in a restrained radial fan within a bounded rounded-rectangle window, each with a two-stop radial gradient (#F7DDE3 → transparent); four hairline radiance strokes radiating from name centre',
        'Petal Window',
        'Strict centred symmetrical vertical column — logo upper quarter, name mid-zone, copy below hairline rules, petal window lower half; typography and motif occupy separate non-overlapping horizontal bands',
        'SOFT_PETALS'),
    '51_B_LIQUID_VEIL': ('Single sinuous vertical Bézier ribbon veil form tapering to pointed finials, filled with a three-stop vertical linear gradient (blush → honey-rose → ivory-transparent); four tiny rose-gold vector dot accents punctuating the type-lane edge as a vertical rhythm',
        'Liquid Veil',
        'Asymmetric two-lane vertical split — dominant veil motif occupies left-of-centre lane running full height; type stack anchored to right lane reading bottom-upward; BBROSE horizontal at top-right shoulder; no centred horizontal banding',
        'RIBBON_FLOW'),
    '51_C_DEWDROP_CONSTELLATION': ('22–30 isolated closed Bézier dewdrop forms in three size classes (near-circular, teardrop, rounded-drop), each with a two-stop radial gradient (white → peach-rose → transparent); sparse-to-dense diagonal arc from lower-left to upper-right cluster',
        'Dewdrop Constellation',
        'Asymmetric diagonal — type column flush upper-left; dewdrop constellation arcs from lower-left edge through mid-face to upper-right cluster; lower-right intentionally sparse; no centred window, no horizontal banding, no vertical lane split',
        'DEWDROP_CONSTELLATION'),
    '52_A_AMBER_NOCTURNE': ('No motif on bottle; single newly designed contour-rose in blind emboss on carton lower quarter only — eight to twelve concentric closed Bézier stroke-only paths, no fill, no raster, original construction',
        'Amber Nocturne',
        'Centred vertical axis; bottle as sole primary subject occupying full frame height; carton angled behind as secondary reveal; generous unprinted glass above and below the tight typographic zone; no peripheral decoration',
        'HALO_RINGS'),
    '52_B_ROSE_SMOKE': ('No decorative motif on bottle or carton; single fine horizontal rule path above product name as the sole graphic element beyond type — restrained editorial structure, no botanical or floral element',
        'Rose Smoke',
        'Asymmetric left-anchored hierarchy on bottle; BBROSE upper-left, dominant name centred-left, sub-name offset right; carton placed back-left at angle; editorial negative space above and flanking the type block; no centred symmetry',
        'EDITORIAL_RULE_SYSTEM'),
    '52_C_NOCTURNE_APOTHECARY': ('No botanical motif; structured grid of fine warm-gold horizontal rule paths and a single vertical accent rule on carton as the sole graphic element beyond type — scientific notation data-block on bottle; precision line system as the decorative identity',
        'Nocturne Apothecary',
        'Structured left-aligned typographic grid on bottle front face; three horizontal rule paths create open/close boundaries for the field; BBROSE hallmark at grid head, dominant name below, scientific notation data-block at grid foot; carton echoes left-margin alignment; no centred or floating layout',
        'EDITORIAL_RULE_SYSTEM'),
    '84_A_PETAL_WINDOW': ('Seven to nine closed Bézier petal-droplet forms clustered in a near-oval window frame, each filled with a blush-to-cream radial gradient at 65% opacity, arranged as an organic overlapping bloom',
        'Petal Window — Controlled Bloom',
        'Vertically stacked three-zone lid: BBROSE lockup anchored top-left / display type block upper-centre / bounded petal-window lower-centre / Arabic name below window; strict bilateral symmetry on the centre axis',
        'SOFT_PETALS'),
    '84_B_LIQUID_VEIL': ('Two overlapping tall vertical vector gradient-mesh veil ribbons, soft-feathered Bézier edges dissolving into the ivory ground, billowing rightward in the lower third, Pale Petal through Warm Cream through blush at 40–75% layered opacity',
        'Liquid Veil — Flowing Vertical Nectar',
        'Asymmetric vertical-spine layout: veil as full-height central motif; product name as left-edge vertical type spine; category word at lower centre; brand lockup at bottom-right; Arabic name floating in upper quarter above the veil density',
        'RIBBON_FLOW'),
    '84_C_DEWDROP_CONSTELLATION': ('Sparse-to-dense dewdrop constellation of closed teardrop Bézier paths, progressing from three to four large drops at lower-left to small isolated drops at upper-right, each filled with a near-white-to-Pale Petal radial gradient simulating a glass bead of rose water',
        'Dewdrop Constellation — Asymmetric Edge Bloom',
        'Asymmetric edge-led diagonal layout: dewdrop constellation anchored lower-left sweeping to upper-right; open negative space on the right half hosts the flush-right type block; brand lockup crowns top-centre; composition has no enclosing frame or central axis symmetry',
        'DEWDROP_CONSTELLATION'),
    '88_A_PETAL_WINDOW': ('Seven to nine closed Bézier petal-droplet vector forms in warm-gold at 65% opacity, radially clustered inside the hairline rose-gold window frame, spot-UV outline on each petal edge',
        'Petal Window — Blush Cipher',
        'Centred front decoration window flanked vertically by bilingual name tiers above and below; BBROSE seal anchors base; type sits outside the window boundary, never over it',
        'SOFT_PETALS'),
    '88_B_LIQUID_VEIL': ('Single continuous compound-Bézier nectar-veil form, Warm Gold at 55% opacity, undulating silhouette narrowing at mid-point, with centre-axis spot-UV gloss stripe suggesting poured liquid',
        'Liquid Veil — Nectar Flow',
        'Vertical asymmetric split: flowing veil occupies centre-left vertical band; typography occupies right-column zone beside veil; BBROSE at top-right, product names mid-right, category copy lower-right — top-to-bottom reading order down one side',
        'RIBBON_FLOW'),
    '88_C_DEWDROP_CONSTELLATION': ('Twelve to twenty-two closed elliptical Bézier dewdrop forms in sparse-to-dense constellation from lower-left, near-transparent blush fill with rose-gold hairline strokes, spot-UV gloss dome caps on three densest droplets, density decreasing toward upper-right until isolated hairline ellipses',
        'Dewdrop Constellation — Edge-Led Galaxy',
        'Strong diagonal tension: constellation dense at lower-left corner, dissipating toward upper-right; type column occupies upper-right open sky zone; asymmetric edge-led composition, no centring anywhere on the lid face',
        'DEWDROP_CONSTELLATION'),
    '89_A_PETAL_WINDOW': ('Seven closed Bézier petal-droplets in a loose radial cluster inside the cartouche window, alternating filled blush and rose-gold outline forms, suggesting a pressed bloom without literal florality',
        'Contour Petal — Controlled Window',
        'Vertically centred cartouche window on lid face, with product names anchored above and below the window in open cream ground; BBROSE wordmark below centre; circular rule ring frames the entire lid',
        'SOFT_PETALS'),
    '89_B_LIQUID_VEIL': ('Six-to-eight sinuous closed Bézier nectar-filament veil strands in a vertical waterfall, fanning outward, grading from blush-fill at centre to rose-gold hairline outlines at outer edge',
        'Nectar Veil — Flowing Vertical',
        'Full-face vertical veil strands flow freely from upper-centre to lid perimeter; wordmark pins the top; bilingual product names anchor the lower third; no contained window or cartouche',
        'RIBBON_FLOW'),
    '89_C_DEWDROP_CONSTELLATION': ('Sparse-to-dense dewdrop constellation of closed Bézier teardrop and sphere paths, grading from dense spot-UV domes at lower-left through rose-gold outlined mid-zone to solid rose-gold foil isolated droplets at upper-right',
        'Dewdrop Constellation — Edge-Led Asymmetric',
        'Asymmetric edge-led constellation originating from lower-left, radiating toward upper-right; typography occupies upper third horizontally and right edge vertically; no centred zone, no contained frame — fully open asymmetric field',
        'DEWDROP_CONSTELLATION'),
    '91_A_PETAL_WINDOW': ('Seven-to-nine slender Bézier teardrop petals arranged in a loose radial fan inside a rose-gold oval cartouche; two petals in rose-gold foil, remaining petals in translucent Deep Rose vector fill; no motif outside the window',
        'Petal Window — Blush Compact',
        'Vertical axis centred: BBROSE wordmark at crown → bilingual name block → oval petal-window cartouche at disc centre → shade arc at rim base; generous blank matte field surrounding the window on all sides',
        'SOFT_PETALS'),
    '91_B_LIQUID_VEIL': ('Single continuous vector gradient veil ribbon with fine parallel Bézier internal stroke lines suggesting laminar liquid flow; veil widens and deepens in opacity as it descends; dominant full-surface motif',
        'Liquid Veil — Ivory Nectar Compact',
        'Asymmetric diagonal: veil ribbon sweeps upper-left to lower-right across the full lid face; wordmark anchored lower-left; name lockup tracks the right arc — three elements in triangulated tension, no central axis hierarchy',
        'RIBBON_FLOW'),
    '91_C_DEWDROP_CONSTELLATION': ('Forty-to-sixty Bézier circle/ellipse droplets in a sparse-to-dense gradient constellation originating at the lower-right edge; large anchor drops with rose-gold foil ring strokes and spot-UV dome fills; micro accent drops in translucent Deep Rose vector fills; fully asymmetric, never centred',
        'Dewdrop Constellation — Peach Glass Compact',
        'Asymmetric edge-led constellation sweeping lower-right (dense) to upper-left (sparse); typography on an L-axis at lower-left and left-edge; wordmark in upper-left negative space; shade numeral embedded in the dense cluster — four elements in radially unbalanced, editorial tension',
        'DEWDROP_CONSTELLATION'),
}


def test_bh67_every_recorded_variation_reads_the_family_its_words_name():
    changed = []
    for key, (motif, title, composition, family) in _RECORDED_VARIATIONS.items():
        got = (cm.classify_family(" ".join([motif, title]))
               or cm.classify_family(" ".join([motif, title, composition])))
        assert got == family, (key, got, family)
        changed += [key] if key.endswith("A_PETAL_WINDOW") else []
    assert len(_RECORDED_VARIATIONS) == 21 and len(changed) == 5


def test_bh67_the_classifier_reads_whole_words_and_a_shape_is_no_family():
    assert cm.classify_family("seven slender teardrop petals in a loose radial fan") == "SOFT_PETALS"
    assert cm.classify_family("petal droplets in a window") == "SOFT_PETALS"            # the house's own coinage
    assert cm.classify_family("a dewdrop constellation of teardrop drops") == "DEWDROP_CONSTELLATION"
    assert cm.classify_family("rose-gold foil ribbon veil") == "RIBBON_FLOW"            # a colour is no flower
    assert cm.classify_family("a single rose bloom") in ("SOFT_PETALS", "FLORAL_ABSTRACT")
    assert cm.classify_family("floral motif") == "FLORAL_ABSTRACT"


def test_bh67_the_petals_are_the_ones_the_words_ask_for():
    rows = {key: cm.petal_parameters(" ".join(v[:2])) for key, v in _RECORDED_VARIATIONS.items()
            if key.endswith("A_PETAL_WINDOW")}
    assert {k: (p["count"], p["arrangement"], p["outline"]) for k, p in rows.items()} == {
        "51_A_PETAL_WINDOW": (8, "fan", "none"), "84_A_PETAL_WINDOW": (8, "radial", "none"),
        "88_A_PETAL_WINDOW": (8, "radial", "none"), "89_A_PETAL_WINDOW": (7, "radial", "alternate"),
        "91_A_PETAL_WINDOW": (8, "fan", "none")}
    assert rows["84_A_PETAL_WINDOW"]["opacity"] == 0.65 and rows["91_A_PETAL_WINDOW"]["width_ratio"] == 0.28
    # the colour-field sentence gives the petals' opacity where the motif sentence does not (task 91)
    assert cm.petal_parameters("seven petals", colour_field="Deep Rose #8B3A52 at 55% vector opacity on interior "
                                                            "petals; rose-gold foil")["opacity"] == 0.55


def test_bh67_a_petal_concept_is_drawn_as_petals_in_the_count_its_words_give():
    structured = {"verified": True, "variation_id": "A_PETAL_WINDOW",
                  "motif_signature": _RECORDED_VARIATIONS["89_A_PETAL_WINDOW"][0],
                  "title": _RECORDED_VARIATIONS["89_A_PETAL_WINDOW"][1]}
    spec = cm.build_motif_spec(structured, _vg(), _zones(), None)
    assert (spec["requested_family"], spec["rendered_via"]) == ("SOFT_PETALS", "petal_bloom")
    nodes = cm.language_for_spec(spec).build((0.0, 0.0, 40.0, 30.0), __import__(
        "apps.ire.design_language", fromlist=["LanguageParameters"]).LanguageParameters(), "front",
        lambda v: v, lambda v: v)
    assert [n.name for n in nodes] == [f"petal-{i}" for i in range(7)]
    assert [n.fill is None for n in nodes] == [False, True, False, True, False, True, False]   # alternating outlines


# --- THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
# "The lid is missing the concept's rule, ring and radial lines." ---------------------------------------------------
#: task 110's own motif words and title (variation A_RADIANT_AXIS, the §BH68(f) concept; verbatim, as
#: ``test_au3_divider_gates._T110_CONCEPT`` holds them)
_T110_RADIAL = ("Radial particle veil: fine Bézier stroked lines emanating from a single centre point behind the type, "
                "each ending in a small filled circular node, all in Blush #F2C4CE at reduced opacity, density "
                "tapering toward the rim", "Radiant Axis")


def test_the_radial_family_moves_the_radial_concept_and_no_recorded_one():
    """RE-MEASURED over every Gate-1 variation on record before the family was landed, the way §BH67(b)1 measured it.
    Task 110's words scored one hit each for POWDER ("particle"), RIBBON ("veil") and EDITORIAL ("lines"), and the tie
    went to the first listed: a powder scatter was drawn where the concept draws rays. With RADIAL_LINES listed before
    POWDER, "emanating" and "centre point" read it two words to one; all 21 recorded variations read exactly as they
    did. The words that were NOT taken, each because it would move a recorded concept: the bare "radial" (six petal
    and dewdrop records say "radial gradient", "radial fan", "radial cluster"), "ray" (RADIANCE_LINES' own) and "focal
    point" (50 B's "radiance hairlines tapering from a mid-left focal point")."""
    for key, (motif, title, composition, family) in _RECORDED_VARIATIONS.items():
        got = (cm.classify_family(" ".join([motif, title]))
               or cm.classify_family(" ".join([motif, title, composition])))
        assert got == family, (key, got, family)
    assert cm.classify_family(" ".join(_T110_RADIAL)) == "RADIAL_LINES"
    for words in ("a blush-to-cream radial gradient", "petals in a loose radial fan", "a radial cluster of petals"):
        assert cm.classify_family(words) != "RADIAL_LINES", words
    assert cm.classify_family(" ".join(_RECORDED_VARIATIONS["50_B_LAYERED_TYPE_FIELD"][:2])) == "RADIANCE_LINES"
    from apps.ire import composer_vocabulary as V
    assert V.family_status("RADIAL_LINES")[:2] == (V.DRAWN, "radial_lines")
    assert V.family_status("RADIANCE_LINES")[:2] == (V.APPROXIMATED, "contour_terrain")      # its route kept


def test_the_rays_are_the_ones_the_words_ask_for():
    """Task 110's rays: each ends in its node ("each ending in a small filled circular node"), they taper toward the
    rim ("density tapering toward the rim"), and "at reduced opacity" — words that give no number — is read as HALF
    (``REDUCED_OPACITY``) and says so; a number in the words is always taken instead; what the words do not give is the
    language's own default and says so. The spec carries it, and the language binds it."""
    spec = cm.build_motif_spec({"verified": True, "variation_id": "A_RADIANT_AXIS", "motif_signature": _T110_RADIAL[0],
                                "title": _T110_RADIAL[1]}, _vg(), _zones(), None)
    assert (spec["requested_family"], spec["rendered_via"], spec["rendered_via_is_approximate"]) == (
        "RADIAL_LINES", "radial_lines", False)
    radial = spec["radial"]
    assert cm.REDUCED_OPACITY == 0.5
    assert {k: radial[k] for k in ("rays", "nodes", "taper", "opacity")} == {
        "rays": 72, "nodes": True, "taper": True, "opacity": 0.5}
    assert "the words give no number" in radial["why"]["opacity"] and "own default" in radial["why"]["rays"]
    assert cm.radial_parameters("fine lines emanating from one centre point at 40% opacity")["opacity"] == 0.4
    plain = cm.radial_parameters("fine lines emanating from one centre point")
    assert (plain["nodes"], plain["taper"], plain["opacity"]) == (False, False, None)
    language = cm.language_for_spec(spec)
    assert language.name == "radial_lines" and language.generators[0].keywords["radial"]["opacity"] == 0.5


# ---------------------------------------------------------------------------------------------------------------
# §BH67(d)1 — "A vision step reads the approved concept and returns its layout as structure … Cost per concept is
# cents; report it. … Where the vision step cannot read an element, it says so and the fixed slot is used — reported,
# never silent." No provider is called here: the call is stood in for, and the record is what is proved.
# ---------------------------------------------------------------------------------------------------------------

def _vision_answer(payload, tin=2400, tout=600):
    import json
    from types import SimpleNamespace
    return SimpleNamespace(usage=SimpleNamespace(input_tokens=tin, output_tokens=tout),
                           content=[SimpleNamespace(type="text", text=json.dumps(payload, ensure_ascii=False))])


#: a read in PIXELS of a 400 x 600 picture whose surface spans (40, 100)-(360, 420): the service turns every box into
#: fractions of that surface
_T91_READ = {"surface": "LID_TOP", "surface_box": [40, 100, 360, 420], "surface_shape": "round",
             "elements": [{"kind": "mark", "box": [160, 132, 240, 148], "align": "centre", "seen_text": "BBROSE",
                           "finish": "rose-gold foil", "confidence": 0.9},
                          {"kind": "name", "box": [136, 164, 264, 196], "align": "centre", "seen_text": "Focus",
                           "confidence": 0.95},
                          {"kind": "name_ar", "box": [168, 200, 232, 220], "align": "centre", "seen_text": "فوكس",
                           "confidence": "high"},
                          {"kind": "window", "box": [144, 228, 256, 356], "align": "centre", "shape": "oval",
                           "confidence": 0.9},
                          {"kind": "wordart", "box": [60, 120, 90, 140]},
                          {"kind": "motif", "box": [300, 380, 390, 590]}],
             "unread": ["ring"], "notes": "seen at an angle"}


def _image(tmp_path, folder="generated"):
    from PIL import Image
    path = tmp_path / folder / "concept.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (400, 600), (250, 243, 236)).save(path)
    return str(path)


def test_bh67d1_the_concept_is_read_as_structure_and_what_cannot_be_vouched_for_is_named(tmp_path):
    from django.test import override_settings
    from apps.pipeline.services import concept_layout as L
    calls = []

    def call(system, content, **kw):
        calls.append(kw)
        return _vision_answer(_T91_READ)
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        rec = L.read_layout(None, image_path=_image(tmp_path), surface="LID_TOP", surface_words="the compact's lid",
                            structured={"typography_signature": "'Focus' over 'فوكس'"}, call=call)
    assert rec["state"] == L.READ and rec["surface_shape"] == "round" and rec["image"]["size_px"] == [400, 600]
    assert [e["kind"] for e in rec["elements"]] == ["mark", "name", "name_ar", "window"]
    assert rec["elements"][1]["seen_text"] == "Focus" and rec["elements"][3]["shape"] == "oval"
    assert all("text" not in e for e in rec["elements"])          # a reading of the picture, never a text to print
    # pixels read against the grid, turned into fractions of the surface: the name's (136,164)-(264,196) on the
    # (40,100)-(360,420) surface is (0.3, 0.2)-(0.7, 0.3)
    assert rec["elements"][1]["box"] == [0.3, 0.2, 0.7, 0.3] and rec["elements"][1]["box_px"] == [136, 164, 264, 196]
    # an undeclared kind and a box mostly off the surface are dropped BY NAME, never kept silently
    assert any("wordart" in p for p in rec["problems"]) and any("(motif)" in p for p in rec["problems"])
    # a confidence that is not a number is named, and the element it came with is kept — the run never crashes on it
    assert rec["elements"][2]["confidence"] is None and any("confidence 'high'" in p for p in rec["problems"])
    assert rec["unread"] == ["ring"] and f"{L.LAYOUT_UNREAD}: ring" in rec["codes"]
    assert rec["margins"]["top"] == 0.1 and rec["balance"]["horizontal"] == "centred"
    # the cost is the ledger's own price table's: 2,400 in and 600 out on the FAST model — cents
    from decimal import Decimal
    from django.conf import settings
    from apps.pipeline.services.cost_ledger import claude_cost_usd
    assert Decimal(rec["cost"]["usd"]) == claude_cost_usd(settings.CLAUDE_MODEL_HEAVY, 2400, 600) < Decimal("0.10")
    assert calls[0]["operation"] == L.OPERATION and calls[0]["model"] == settings.CLAUDE_MODEL_HEAVY


def test_bh67d1_a_failed_read_and_a_reference_image_are_states_with_reasons_and_no_call_is_made_for_the_second(
        tmp_path):
    from django.test import override_settings
    from apps.pipeline.services import concept_layout as L

    def broken(*a, **k):
        raise RuntimeError("no network in tests")
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        rec = L.read_layout(None, image_path=_image(tmp_path), surface="LID_TOP", surface_words="the lid",
                            structured=None, call=broken)
        assert rec["state"] == L.FAILED and "RuntimeError" in rec["why"] and rec["elements"] == []
        assert rec["codes"] == [f"{L.LAYOUT_UNREAD}: the vision call failed"]

        def must_not_run(*a, **k):
            raise AssertionError("a REFERENCE image was sent to a model")
        ref = L.read_layout(None, image_path=_image(tmp_path, "references"), surface="LID_TOP",
                            surface_words="the lid", structured=None, call=must_not_run)
    assert ref["state"] == L.REFUSED and ref["codes"][0].startswith(L.LAYOUT_REFUSED_REFERENCE)
    assert L.read_layout(None, image_path=str(tmp_path / "absent.png"), surface="LID_TOP", surface_words="",
                         structured=None)["state"] == L.UNREAD


def test_bh67d1_a_read_is_cached_on_the_image_and_the_layout_measure_is_a_number_per_element(tmp_path):
    from django.test import override_settings
    from apps.pipeline.services import concept_layout as L
    n = []

    def call(system, content, **kw):
        n.append(1)
        return _vision_answer(_T91_READ)
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        img = _image(tmp_path)
        first = L.cached_or_read(None, {}, image_path=img, surface="LID_TOP", surface_words="", structured=None,
                                 call=call)
        again = L.cached_or_read(None, {L.SPEC_KEY: first}, image_path=img, surface="LID_TOP", surface_words="",
                                 structured=None, call=call)
    assert len(n) == 1 and again["cached"] is True and again["elements"] == first["elements"]
    rows = {r["element"]: r for r in L.measure(first, {"name": [0.35, 0.25, 0.65, 0.3], "mark": [0.3, 0.8, 0.7, 0.9],
                                                       "ring": [0.05, 0.05, 0.95, 0.95]})}
    assert rows["name"]["state"] == "MEASURED" and rows["name"]["dx"] == 0.0 and rows["name"]["dy"] == 0.025
    assert rows["name"]["width_ratio"] == 0.75 and rows["name"]["height_ratio"] == 0.5
    assert rows["mark"]["distance"] == 0.725
    assert rows["ring"]["state"] == "NOT_IN_CONCEPT" and rows["window"]["state"] == "NOT_DRAWN"


def test_his_look_the_house_constellations_star_is_the_one_sparkle():
    """His look at 117 drawn from its map (2026-10-02): small designs like the sparkles "always inconsistent. And not
    looking good". The house powder constellation's four-point star is the one sparkle every drawing draws — curved
    arms, the house pinch and tip, one shape at every size — never a straight-sided polygon."""
    import random

    from apps.ire import design_language as DL
    from apps.ire.graph import CubicTo, LineTo
    groups = DL.gen_powder_constellation((0.0, 0.0, 80.0, 60.0), DL.LanguageParameters(), random.Random(3),
                                         lambda x: x, lambda y: y)
    stars = [n for g in groups for n in g.children if n.name.endswith("-star")]
    assert stars
    shapes = []
    for n in stars:
        assert sum(isinstance(sg, CubicTo) for sg in n.segments) == 4                   # four curved sides …
        assert sum(isinstance(sg, LineTo) for sg in n.segments) <= 4                    # … straight only at tips
        xs = [v for sg in n.segments for v in (getattr(sg, "x", None), getattr(sg, "x1", None), getattr(sg, "x2", None))
              if v is not None]
        ys = [v for sg in n.segments for v in (getattr(sg, "y", None), getattr(sg, "y1", None), getattr(sg, "y2", None))
              if v is not None]
        cx, cy, r = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, (max(xs) - min(xs)) / 2
        shapes.append([round((x - cx) / r, 6) for x in xs] + [round((y - cy) / r, 6) for y in ys])
    assert all(shape == shapes[0] for shape in shapes)

