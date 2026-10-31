"""Verbatim replica of the task-#50 retry's rejected direction set
(AgentLog 806, code revision c8294ab) — the fixture for offline
revalidation under the 2A-6D-CORR-2 corrected validators. Field values
are byte-identical to the captured payload; do not edit them."""

AGENTLOG_806_DIRECTIONS = [
    {
        "name": "Editorial Soft Radiance",
        "risks": "Condensed editorial style may read as fashion rather than beauty in some markets; ensure BAKED POWDER type and BBROSE logo scale reads as cosmetic packaging, not editorial magazine cover.",
        "typography": "Condensed editorial sans-serif (style of narrow grotesque, e.g. Dharma Gothic Condensed) for BAKED POWDER in bold uppercase. BBROSE uses official fixed lockup only. POLVO HORNEADO and LUMINOSIDAD SUAVE in lighter-weight neutral sans-serif at 40–50% the x-height of the product name.",
        "design_axis": "Typography-led: expressive large condensed type IS the primary visual element; decoration is a disciplined footnote.",
        "prompt_seed": "An asymmetric editorial carton front in ivory and blush pink; oversized condensed bold uppercase BAKED POWDER stacked across two lines dominates the center field; BBROSE wordmark sits top-left; a single fine rose-gold hairline rule and eight micro powder dots are the only ornament; generous white space, modern and quietly feminine.",
        "color_system": "Base: ivory (#FAF3EC, ~70%). Secondary: light blush pink (#F2C4CE, ~22%). Accent: rose-gold foil or warm gold as restrained rule and dot (~8%). Black and navy prohibited as dominant.",
        "direction_id": "d1",
        "subject_story": "Baked powder pressed and kissed by warm light; fine pigment lifted into the air as a barely-there shimmer. The editorial confidence of the typography mirrors the formula's clean, skin-perfecting performance.",
        "emotional_tone": "Cool editorial confidence, modern, clean, commercially legible, quietly feminine.",
        "focal_hierarchy": "1. BAKED POWDER (largest, condensed bold). 2. BBROSE wordmark. 3. POLVO HORNEADO and LUMINOSIDAD SUAVE (small, grouped). 4. Radiance rule and dot accent (supporting).",
        "graphic_elements": "One fine horizontal or diagonal hairline rule (~1 pt). A cluster of 8–12 micro circular powder dots (1–2 mm each) positioned near the BAKED POWDER baseline. Total decorative coverage: under 10% of visible area. Zero raster elements.",
        "imagery_approach": "No photography. No compact. No illustration. Pure typographic composition with minimal vector accents only.",
        "layout_structure": "Asymmetric three-row editorial grid. BBROSE wordmark top-left at roughly 40% panel width. BAKED POWDER stacked in two compressed lines dominating the central field. POLVO HORNEADO and LUMINOSIDAD SUAVE in small tight sans-serif at lower-left, right-aligned against a thin vertical rule. A single horizontal hairline separates the brand zone from the product-name zone.",
        "concept_statement": "Typography is the artwork. An asymmetric editorial grid stacks BAKED POWDER in large condensed uppercase across the front face. A single fine radiance rule and a scatter of micro powder dots — the only decoration — evoke the silky luminosity of pressed baked pigment without any illustration or spiral motif.",
        "originality_notes": "Asymmetric editorial grid and condensed-type dominance are not present in any of the four reference productions. Radiance hairline and micro-dot motif are unique to this direction. No spiral, no compact photograph, no centered illustration field.",
        "product_target_fit": "Strong shelf presence in multi-brand cosmetics retail; reads instantly across Middle Eastern and Southern African markets without cultural narrowing.",
        "prohibited_choices": [
            "No baked-powder compact spiral or photographed compact.",
            "No centered symmetrical layout — this direction is asymmetric.",
            "No heavy floral or botanical illustration.",
            "No decorative coverage exceeding 10% of visible area.",
            "No copying the Concealer ghost-watermark oversized background text convention."
        ],
        "material_finish_direction": "Matte soft-touch laminate. Spot UV on BAKED POWDER letterforms. Light embossing on BBROSE wordmark. No heavy gold coverage.",
        "target_structural_guidance": "Front face is self-contained. A cropped condensed letterform from BAKED POWDER may bleed subtly onto one side panel as a continuation element. Back panel is typographically quiet with clearly structured regulatory placeholder zones. STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED."
    },
    {
        "name": "Geometric Halo",
        "risks": "Sky-blue ground may read as skincare or pharmaceutical in some markets; counter by ensuring BAKED POWDER type is prominent and BBROSE is treated with champagne warmth.",
        "typography": "High-contrast serif (style of Cormorant or Freight Display) for BAKED POWDER in elegant uppercase, medium weight. BBROSE fixed official lockup. POLVO HORNEADO and LUMINOSIDAD SUAVE in thin neutral sans-serif, small, open tracking.",
        "design_axis": "Pattern and structure-led: a precise geometric arc motif anchors the composition; typography reads inside and below the halo crown.",
        "prompt_seed": "A centered carton front in light sky blue; three to five thin concentric partial arcs form a quiet geometric halo in pale champagne at the panel center; a high-contrast serif BAKED POWDER sits beneath the halo crown; BBROSE wordmark in ivory above; the remaining field is open, calm and architecturally luminous.",
        "color_system": "Base: light sky blue (#D6EAF8, ~68%). Secondary: warm ivory (#FAF3EC, ~22%). Accent: pale champagne gold on outermost halo arc stroke (~10%). Black and navy prohibited as dominant.",
        "direction_id": "d2",
        "subject_story": "Baked powder diffuses light like a soft corona; the geometric halo renders that optical phenomenon as elegant controlled line-work — the physics of radiance made visible without illustration.",
        "emotional_tone": "Serene, luminous, internationally elegant, spa-calm, architecturally refined.",
        "focal_hierarchy": "1. Geometric halo arcs (structural anchor, draws eye first). 2. BAKED POWDER (serif type below halo). 3. BBROSE wordmark (above halo). 4. POLVO HORNEADO and LUMINOSIDAD SUAVE (lower, supporting).",
        "graphic_elements": "3–5 concentric partial arcs, stroke weight 0.5–1 pt, pale champagne or white, centered on panel. Total halo coverage under 18%. One arc may be interrupted at midpoint to allow type to sit inside. Zero raster elements.",
        "imagery_approach": "No photography. No compact illustration. No flowing powder cloud or particles. Pure geometric linework only.",
        "layout_structure": "Centered and balanced. BBROSE wordmark upper-center at ~40% panel width. Below it, 3–5 thin concentric partial arcs form a halo occupying roughly 30% of panel height and 45% of panel width. BAKED POWDER in high-contrast serif centered immediately below the halo. POLVO HORNEADO and LUMINOSIDAD SUAVE in restrained small-scale sans-serif below, centered.",
        "concept_statement": "Soft luminosity translated into pure geometry. A set of thin concentric arcs forms a restrained centered halo — a radiant crown of light echoing the warm glow baked powder deposits on skin. The halo occupies under 20% of the face; the rest is clean sky-blue-tinted light.",
        "originality_notes": "Thin-arc halo motif does not appear in the Colorete, Lip Balm, Concealer or Lip Oil references. Sky-blue palette is distinct from all four reference productions. High-contrast serif pairing not used in any reference.",
        "product_target_fit": "Centered symmetry and cool blue-ivory palette translate cleanly across Middle Eastern and Southern African retail contexts; sky-blue base differentiates strongly from blush-dominant D1.",
        "prohibited_choices": [
            "No compact photograph inside or behind the halo.",
            "No powder particles or flowing veil — this direction uses arcs only.",
            "No asymmetric editorial composition — this direction is centered.",
            "No decorative coverage exceeding 20% of visible area.",
            "No blush pink or peach dominant — palette is sky blue, ivory and champagne."
        ],
        "material_finish_direction": "Matte laminate. Restrained gold stamping on outermost halo arc only. Optional shallow debossing on inner arc group. No spot UV on this direction.",
        "target_structural_guidance": "One or two halo arcs may continue partially onto an adjacent side panel at reduced opacity. Back panel is visually quiet; no halo behind regulatory text. STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED."
    },
    {
        "name": "Powder Drift",
        "risks": "If particle count is too high or paths too dense the 20% coverage limit will be breached and the design will read as smoky; particle count and path length must be validated at artwork stage before Gate-2 review.",
        "typography": "Rounded geometric sans-serif (style of Poppins or Nunito) for BAKED POWDER and all panel copy — materially different from D1 condensed grotesque and D2 high-contrast serif. Weight: medium-bold for product name, light for Spanish copy. Letter-spacing: open and relaxed.",
        "design_axis": "Motif and movement-led: a directional abstract particle stream is the structural logic; typography occupies the clear open field above the drift.",
        "prompt_seed": "A warm ivory carton front; BBROSE wordmark at top center, BAKED POWDER in rounded medium-bold sans-serif below it in the clear upper field; a sparse diagonal stream of soft peach and mint vector particles and short curved brush-stroke paths rises from the lower-left corner toward the center, leaving most of the face open and luminous; modern, adult and sensory.",
        "color_system": "Base: warm ivory (#FAF3EC, ~65%). Secondary: light peach (#FDDDB4, ~20%). Tertiary: soft mint (#C8E6C9, ~8% in coolest particles for warm-cool dimension). Spot UV sheen on selected particles (~7%). Black and navy prohibited as dominant.",
        "direction_id": "d3",
        "subject_story": "A makeup brush lifts warm peach-toned baked powder upward in a soft diagonal veil: fine particles catch light as they travel then dissolve into clean space. The subject is the sensory moment of application.",
        "emotional_tone": "Warm, light, sensory, approachable, quietly adult, fresh and internationally modern.",
        "focal_hierarchy": "1. BBROSE wordmark (top, clear field). 2. BAKED POWDER (large, above drift). 3. Powder drift particle stream (mid-lower panel). 4. POLVO HORNEADO and LUMINOSIDAD SUAVE (between wordmark and drift).",
        "graphic_elements": "18–28 individual vector dot particles (circles 1–3 mm, varied sizes). 4–7 short curved Bézier flow paths (stroke 0.5–0.8 pt) suggesting brush-sweep direction. Each element is a discrete repositionable vector object. Total decorative coverage under 20%. Zero raster elements.",
        "imagery_approach": "No photography. No compact. No halo arcs. No condensed editorial type dominance. Pure vector motion: particles and curved paths only.",
        "layout_structure": "Diagonal movement begins at lower-left corner; sparse particle stream travels at roughly 45° toward panel center, stopping before the upper two-thirds. Upper portion is fully clear: BBROSE wordmark upper-center, BAKED POWDER below it in rounded sans-serif, POLVO HORNEADO and LUMINOSIDAD SUAVE beneath that. Particles and flow paths occupy the lower panel zone only.",
        "concept_statement": "Directional movement. A controlled sparse stream of vector particles and short flowing Bézier paths rises diagonally from a lower corner toward the center — a visual metaphor for baked powder swept across skin in one soft warm stroke. Most of the front remains open and light.",
        "originality_notes": "Diagonal corner-led particle drift is not present in any of the four reference productions. Peach-mint-ivory palette is not used in any reference. Rounded humanist sans-serif family is distinct from the scripts and grotesques in all references.",
        "product_target_fit": "Peach and mint palette reads as fresh and modern across Middle Eastern and Southern African markets; diagonal movement gives shelf energy without being childish.",
        "prohibited_choices": [
            "No centered geometric halo — this direction uses diagonal corner movement only.",
            "No condensed editorial large-type grid.",
            "No compact photograph or baked-powder spiral imagery.",
            "No raster texture sheet simulating powder — particles must be discrete vectors.",
            "No decorative coverage exceeding 20% of visible area.",
            "No blush pink or sky blue as dominant — palette is peach, mint and ivory."
        ],
        "material_finish_direction": "Matte laminate. Selective spot UV on 4–6 larger particles for gloss-on-matte shimmer. Minimal embossing on BAKED POWDER product name. Gold stamp on BBROSE wordmark only if desired at single restrained weight.",
        "target_structural_guidance": "Particle stream may continue sparsely onto one adjacent side panel — a few trailing particles only. Back panel is clear; no particles behind regulatory text. STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED."
    }
]
