"""Verbatim replicas from the planner's rejected attempts on tasks 106 and 109 (AgentLog 1844 and 1865, code revision
8294fa6) — the fixtures for the owner's second answer of 2026-09-25: "The planner refusals on tasks 106 and 109. Task
106 is caused by your own repair wording." TASK_106 holds the one direction the planner rewrote on its second attempt
with the repair's own phrase; TASK_109 both attempts whole, the brief and the record's dimensions. Every value is
byte-identical to the captured payload (read-only, 2026-09-25); do not edit them."""

TASK_106 = {'agentlog': 1844,
 'attempt': 2,
 'codes': ['PRODUCTION_RASTER_DEPENDENCY:direction[0]'],
 'direction_0': {'name': 'Silk Veil',
                 'risks': 'Veil ribbons at compact lid scale may require careful weight calibration to avoid looking '
                          'like abstract streaks. Spot UV budget must be confirmed early.',
                 'typography': 'English name: high-contrast transitional serif (Bodoni style), regular weight, '
                               'generous tracking. Arabic name: refined Naskh, optically matched cap-height to '
                               'English. Claims: humanist sans, tight, bilingual paired lines. All typefaces must '
                               'carry full Arabic character set.',
                 'design_axis': 'Typography-led: the bilingual name stack (English serif above, Arabic Naskh below '
                                'at equal scale) is the first read; the veil ribbons are the atmospheric ground '
                                'behind and through it.',
                 'prompt_seed': 'A shallow round pressed-powder compact on a pale cream surface, warm diffused '
                                'side-light illuminating the physical product. The lid face shows three wide '
                                'translucent blush-to-cream Bézier ribbon sweeps across a warm cream ground, with a '
                                'refined bilingual serif-and-Naskh product name centred in the mid-field and a rose '
                                'gold foil BBROSE lockup at the top. Intimate, luminous, composed.',
                 'color_system': 'CS-001 Blush Core. Ground: Warm Cream (#FAF3EC). Veil ribbons: Blush (#F2C4CE) to '
                                 'Pale Petal (#F7DDE3) in graduated opacity. Typography: Deep Rose (#8B3A52). Rose '
                                 'Gold foil on BBROSE lockup and a single ribbon highlight.',
                 'direction_id': 'd1',
                 'subject_story': "Pressed powder's defining sensory act is the moment the puff lifts and deposits a "
                                  'translucent veil. Wide, sweeping vector ribbons in graduated opacity from blush '
                                  'to warm cream simulate that veil — the motif is inseparable from this product '
                                  'category.',
                 'emotional_tone': 'Composed, intimate, luminous. The feeling of pressing a soft powder puff to skin '
                                   'and seeing the veil settle — refined and modern.',
                 'focal_hierarchy': 'Eye enters at the stacked bilingual name, moves into the veil ribbon field, '
                                    'ascends to the BBROSE lockup.',
                 'graphic_elements': 'Three to five wide Bézier ribbon paths crossing the lid face diagonally from '
                                     'lower-left to upper-right, graduating from opaque blush to near-transparent '
                                     'pale petal. Fine single-weight contour lines trace the innermost ribbon edge. '
                                     'A particle scatter of micro-dots at ribbon edges suggests powder dispersion — '
                                     'all drawn as vector ellipses.',
                 'hierarchy_family': 'NAME_FIRST',
                 'imagery_approach': 'Concept render: a studio photograph of the compact resting on a pale cream '
                                     'surface with warm diffused side-light — the physical product is the subject of '
                                     'the photography. The printed lid decoration (the Bézier ribbon artwork) is '
                                     'described separately and contains no photographic element whatsoever.',
                 'layout_structure': 'Lid face: BBROSE lockup at the top in a narrow header band; bilingual name '
                                     'centred in the mid-field, seated within layered veil ribbons; a fine claims '
                                     'line at the base in a compact sans. Body band: shade name in English and '
                                     'Arabic, rose-gold rule. Base: net weight, regulatory minimum.',
                 'concept_statement': 'Pressed powder rendered as a liquid-silk veil: sweeping Bézier ribbons '
                                      'diffuse across the lid face like a breath of finely milled pigment settling '
                                      'on skin. The composition is typography-led — the bilingual product name is '
                                      'the structural spine, held within the veil field. All surface decoration is '
                                      'built from live vector paths and gradients with zero raster dependency.',
                 'originality_notes': 'Ribbon form is distinct from sunburst rays (FB5812) and from the kawaii '
                                      'fields (BP6003). The diagonal sweep avoids the centred-circle convention of '
                                      'the compact pan references.',
                 'product_target_fit': 'The wide ribbon motif reads at compact scale without becoming muddy; the '
                                       'bilingual name centred in the field ensures equal language presence; matte '
                                       'laminate with spot UV is consistent with premium face-powder positioning.',
                 'prohibited_choices': ['No sunburst or ray pattern derived from any prior BBROSE face powder SKU.',
                                        'No butterfly or floral icon — reserved for other house SKUs.',
                                        'No photographic silk texture or raster image printed on the lid; all ribbon '
                                        'effects are Bézier vector paths only.',
                                        'No Arabic set smaller or lighter than the English product name.'],
                 'material_finish_direction': 'Matte soft-touch laminate across all surfaces. Rose gold hot-foil on '
                                              'BBROSE lockup. Spot UV varnish traces the outermost ribbon contour on '
                                              'the lid face — creates a gloss-over-matte finish contrast readable at '
                                              'shelf.',
                 'native_reconstruction_plan': 'Printed decoration rebuilt entirely from native vector primitives '
                                               'with zero decorative rasters. (1) Live typography: transitional '
                                               'serif for English name, Naskh for Arabic name, humanist sans for '
                                               'claims — all editable live text, no outlined raster glyphs. (2) Veil '
                                               'ribbons: three to five filled closed Bézier paths with linear '
                                               'gradient fills from #F2C4CE to #F7DDE3 at varying opacity levels, '
                                               'stacked in layer order in Illustrator — no photographic texture, no '
                                               'raster gradient mesh. (3) Particle scatter: small solid ellipses '
                                               '(0.4–0.8pt diameter) distributed along ribbon edges using a vector '
                                               'scatter brush or manually placed symbol instances — all vector '
                                               'objects. (4) Contour accent: a single open Bézier path at 0.25pt '
                                               'stroke weight in Deep Rose tracing the innermost ribbon. (5) Finish '
                                               'masks: the spot UV plate is a duplicate closed Bézier path matching '
                                               'the outermost ribbon contour, exported as a fifth colour separation '
                                               '— pure vector. The rose gold foil mask is the BBROSE lockup compound '
                                               'path exported as a fourth colour plate. (6) Concept-render-only '
                                               'elements: the studio photograph of the physical compact on a pale '
                                               'cream surface with warm side-lighting exists solely in the concept '
                                               'render presentation file and is never part of any print-production '
                                               'artwork file. The printed lid surface is 100% native vector.',
                 'target_structural_guidance': 'Lid face is the hero panel. Body band is narrow — motif should not '
                                               'migrate there at full scale; a reduced single ribbon or rule is '
                                               'sufficient. Base panel carries regulatory copy only.'}}

TASK_109 = {'agentlog': 1865,
 'brief': {'brand': 'BBROSE',
           'market': '',
           'audience': '',
           'dimensions': '',
           'references': ['A pressed face powder for BBROSE, working name FOCUS. THE PRODUCT. A single pan of '
                          'pressed powder in a shallow round compact with a mirror in the lid, sold in its own '
                          'folding carton. The carton is th'],
           'product_name': 'Focus Pressed Powder',
           'design_target': 'product_container',
           'required_copy': [],
           'preferred_colors': [],
           'preferred_styles': [],
           'product_category': 'CO',
           'prohibited_colors': [],
           'prohibited_motifs': [],
           'production_constraints': []},
 'record_dimensions_mm': [170.5, 18.0, 122.5],
 'attempts': [{'attempt': 1,
               'codes': ['MOTIF_NOT_DISTINCT',
                         'TYPOGRAPHY_NOT_DISTINCT',
                         'PRODUCTION_RASTER_DEPENDENCY:direction[1]'],
               'design_intent': {'hierarchy': 'Brand name (BBROSE lockup) anchors trust; product name FOCUS commands '
                                              'the primary read zone in both English and Arabic with equal weight; '
                                              'claims and shade name occupy a secondary band; regulatory copy fills '
                                              'remaining surface area legibly.',
                                 'confidence': 'HIGH',
                                 'composition': 'The compact lid is the hero surface. A clear horizontal structure: '
                                                'brand lockup in the upper register, product name in dual-language '
                                                'symmetry occupying the center, a powder-veil motif bleeding '
                                                'edge-to-edge beneath or behind the type. Closure and body colour '
                                                'reinforce the finish language.',
                                 'focal_point': 'The powder-veil motif — an abstract field expressing finely milled '
                                                'silk particles, translucent layers or a composed micro-radiance — '
                                                'is the subject anchor. It must be specific to pressed powder, not a '
                                                'generic floral or geometric filler.',
                                 'color_strategy': 'Draw from CS-001 Blush Core or CS-002 Nude Warm, chosen per '
                                                   'direction. Rose gold metallic as a detail finish on logo and '
                                                   'accent lines. No neon, no cold grey, no budget-mass colour '
                                                   'flags.',
                                 'motif_strategy': 'The hero motif must express pressed powder: silkiness, '
                                                   'micro-particle veil, layered translucence, or a radial bloom of '
                                                   'fine pigment. Rendered as native vector — contour lines, '
                                                   'translucent gradient veils, particle fields, soft radial strokes '
                                                   '— never a photographic fill.',
                                 'imagery_strategy': 'Concept render uses clean studio photography of the physical '
                                                     'compact (warm diffuse light, silk surface, rose gold '
                                                     'reflection). The printed decoration is 100% native-vector: no '
                                                     'photographic field on the container surface.',
                                 'visual_objective': 'Design the Focus Pressed Powder compact container — its '
                                                     'applied label zones, body colour and closure finish — as a '
                                                     'studio packshot. The container must communicate a composed, '
                                                     'skin-finished softness: the subject story is pressed powder '
                                                     'itself — silkiness, weightless coverage, the veil of finely '
                                                     'milled pigment suspended in air. Every surface decision must '
                                                     'make the pack feel like a finished face.',
                                 'forbidden_choices': ['Photographic fields as printed decoration on the container '
                                                       'surface.',
                                                       'Neon, cold grey, gender-neutral-tech palettes.',
                                                       'Kawaii cartoon mascots or illustrated characters.',
                                                       'Copying any historical BBROSE dieline layout composition as '
                                                       'a template.',
                                                       'Raster textures required for the design identity.'],
                                 'source_references': ['CS-001 Blush Core — canonical palette and rose gold metallic '
                                                       'role.',
                                                       'CS-002 Nude Warm — alternative warm nude palette option.',
                                                       'ML-001 Glossy Acrylic — lid finish option.',
                                                       'ML-HC-001 Matte Soft Touch PET — body finish option.',
                                                       'AL-001 Soft Luxury — aesthetic and lighting language for '
                                                       'concept render.'],
                                 'typography_strategy': 'Two type families minimum: a refined serif or editorial '
                                                        "display for English 'FOCUS', a calligraphic or high-quality "
                                                        'Arabic display face for the Arabic name — both weighted '
                                                        'equally and optically balanced. Supporting body copy in a '
                                                        'legible humanist sans in both scripts. Shade name set in a '
                                                        'contrasting italic or light-weight register.',
                                 'unresolved_questions': ['Confirm final Arabic product name translation and '
                                                          'calligraphic style approval.',
                                                          'Confirm whether lid surface is acrylic gloss or matte PET '
                                                          'before spot UV planning.',
                                                          'Shade range count: how many SKU colourways must the '
                                                          'system accommodate?',
                                                          'Confirm regulatory copy language requirements per '
                                                          'territory (Arabic/English split).'],
                                 'audience_interpretation': 'Middle-Eastern beauty consumers in Jordan, Syria, '
                                                            'Palestine, Lebanon and Tunisia who read Arabic as a '
                                                            'primary script. The pack must treat Arabic and English '
                                                            'with equal typographic authority — not a hierarchy '
                                                            'where Arabic is a footnote. Buyers expect a premium, '
                                                            'feminine, shelf-credible compact that feels composed '
                                                            'and edited rather than playful or loud.',
                                 'originality_constraints': ['Do not copy the kawaii mascot or cartoon character '
                                                             'language from BP6003 or FB2056.',
                                                             'Do not reproduce the sunburst ray pattern from FB5812.',
                                                             'Do not reproduce the starburst badge composition from '
                                                             'FB3093 Super Stay.',
                                                             'Do not use a bold stacked all-caps powder name layout '
                                                             'that directly echoes SF-2049 Loose Powder.'],
                                 'material_finish_direction': 'Matte soft-touch body with spot UV or gloss varnish '
                                                              'over the motif zone for a tactile finish contrast. '
                                                              'Rose gold foil on BBROSE lockup and key accent '
                                                              'strokes. Options per direction include full gloss '
                                                              'acrylic lid, matte PET body, or pearl-white satin '
                                                              'finish.',
                                 'target_structural_guidance': 'This is a PRODUCT CONTAINER design — a shallow round '
                                                               'pressed-powder compact (lid plus body). Design the '
                                                               'lid label, body band and closure finish. Do not '
                                                               'design a folding carton or dieline. The compact is '
                                                               'approximately 170.5 mm wide, 18 mm deep and 122.5 mm '
                                                               'tall in its shelved orientation; the lid face is the '
                                                               'dominant design surface.'},
               'directions': [{'name': 'Silk Veil',
                               'risks': 'Ribbon arcs must be geometrically resolved to avoid looking generic. Arabic '
                                        'and English type sizing requires careful optical calibration — a type '
                                        'specialist review is advised before final art.',
                               'typography': "English 'FOCUS': high-contrast didone serif, large, tracked wide, Deep "
                                             'Rose ink. Arabic name: matching-weight calligraphic display Arabic, '
                                             'same optical size, same Deep Rose. Supporting copy and shade name: '
                                             'humanist sans-serif, light weight, both scripts.',
                               'design_axis': 'Typography-led — the dual-language FOCUS name in large display type '
                                              'is the first event the eye reads; the veil motif is the field it '
                                              'commands.',
                               'prompt_seed': 'A shallow round pressed-powder compact on a warm blush silk surface, '
                                              'warm diffuse studio light. The gloss lid reveals a layered '
                                              'translucent ribbon field in blush and pale petal tones — abstract '
                                              'powder-sweep arcs — behind a large, equal-weight bilingual FOCUS name '
                                              'in deep rose didone and calligraphic Arabic. Rose gold foil BBROSE '
                                              'lockup at top, shade name at base. Composed, editorial, feminine '
                                              'luxury.',
                               'color_system': 'CS-001 Blush Core: Warm Cream (#FAF3EC) body, Blush (#F2C4CE) '
                                               'primary veil gradient, Pale Petal (#F7DDE3) secondary ribbon layer, '
                                               'Deep Rose (#8B3A52) for type, Rose Gold foil on BBROSE lockup and '
                                               'hairline rule.',
                               'direction_id': 'd1',
                               'subject_story': 'Pressed powder as a sheer, silky veil. The decoration is built '
                                                'entirely from layered translucent Bézier ribbons — abstract '
                                                'powder-sweep arcs — that mimic the trail of a brush through fine '
                                                'pigment. The motif is specific: it cannot be mistaken for water, '
                                                'oil or floral.',
                               'emotional_tone': 'Composed, editorial, quietly confident — a face that is finished '
                                                 'and ready.',
                               'focal_hierarchy': 'Eye enters at the large bilingual FOCUS name, drops through the '
                                                  'veil field, lands on the BBROSE lockup above and the shade name '
                                                  'below.',
                               'graphic_elements': 'Three to five overlapping Bézier ribbon arcs in translucent '
                                                   'Blush and Pale Petal gradients — narrow at entry, widening — '
                                                   'expressing a powder-brush sweep. Particle field of micro-dots at '
                                                   'ribbon termination points. Rose-gold hairline rules at base and '
                                                   'beneath lockup.',
                               'hierarchy_family': 'NAME_FIRST',
                               'imagery_approach': 'Concept render: compact photographed in warm diffuse light on a '
                                                   'silk blush surface. The lid veil is seen through the gloss lid '
                                                   'material. Printed decoration is 100% vector — no photographic '
                                                   'element.',
                               'layout_structure': 'Lid surface: BBROSE lockup small, upper center. Below it, '
                                                   "'FOCUS' in large English serif stacked above its Arabic "
                                                   'equivalent at equal optical weight, both center-aligned. The '
                                                   'powder-veil ribbon field bleeds behind and below the type to the '
                                                   'lower edge. A narrow rose-gold hairline rule separates the name '
                                                   'zone from a slim shade-name band at the base.',
                               'concept_statement': 'The lid is a study in pressed-powder silence: a wide '
                                                    'translucent vector-veil field — flowing Bézier ribbons in '
                                                    'layered blush gradients — reads like the moment fine powder is '
                                                    'swept across skin. Type is the event that cuts through the '
                                                    'softness, large and composed.',
                               'originality_notes': 'Ribbon arcs are abstract powder-sweeps, not rose petals, not '
                                                    'liquid. The bilingual name stacking is a new composition, not '
                                                    'echoing any prior BBROSE face powder layout.',
                               'product_target_fit': 'High: the ribbon-veil motif is specific to pressed powder; the '
                                                     "bilingual name hierarchy directly answers the brief's "
                                                     'equal-weight Arabic requirement.',
                               'prohibited_choices': ['Do not render the ribbons as photographic silk or raster '
                                                      'texture.',
                                                      'Do not position the Arabic name as a smaller subtitle below '
                                                      'the English.',
                                                      'Do not use a sunburst or ray pattern — that is FB5812 '
                                                      'territory.',
                                                      'Do not add kawaii characters or playful badge shapes.'],
                               'material_finish_direction': 'Gloss acrylic lid (ML-001) so the veil reads with '
                                                            'depth. Matte soft-touch body. Rose gold hot-foil stamp '
                                                            'on BBROSE lockup. Spot UV gloss varnish over the ribbon '
                                                            'arcs for tactile contrast against the matte inner band.',
                               'native_reconstruction_plan': 'PRINTED DECORATION: (1) Live type: BBROSE lockup as '
                                                             'fixed vector artwork, rose-gold foil variant; FOCUS in '
                                                             'didone serif OpenType, Arabic name in calligraphic '
                                                             'OpenType Arabic — both live, no outlines required '
                                                             'until final; supporting copy in humanist sans, live. '
                                                             '(2) Veil motif: three to five Bézier path ribbons, '
                                                             'each a gradient mesh from Blush to Pale Petal at '
                                                             '40–70% opacity, stacked on a Warm Cream ground — no '
                                                             'raster. (3) Particle field: small vector ellipses, '
                                                             'uniform radius, scattered at ribbon ends via pattern '
                                                             'or step-repeat — no raster. (4) Hairline rules: 0.25 '
                                                             'pt vector strokes in Rose Gold swatch. (5) Finish '
                                                             'masks: spot UV shape = union of all ribbon paths, '
                                                             'output as separate vector layer; foil mask = BBROSE '
                                                             'lockup outline path. (6) Concept-render-only: gloss '
                                                             'lid reflections, silk surface, ambient warm light — '
                                                             'these are photography or 3D render, never printed. (7) '
                                                             'Confirmation: zero decorative rasters required in the '
                                                             'printed decoration.',
                               'target_structural_guidance': 'Design the compact lid (dominant circular face), the '
                                                             'narrow body band, and the closure rim. The lid carries '
                                                             'all decorative artwork. The body band carries shade '
                                                             'name and four claims in both scripts. Closure rim in '
                                                             'rose gold finish.'},
                              {'name': 'Poudre Engraved',
                               'risks': 'Dense linework must be tested at production scale — lines may close up if '
                                        'printed at hairline weights on matte substrate. Recommend a press proof '
                                        'before finalising line spacing.',
                               'typography': "English 'FOCUS': compact high-contrast serif, moderate scale, Cocoa "
                                             'Rose. Arabic name: structured Naskh or modernist Kufi display, same '
                                             'optical size, Cocoa Rose — side-by-side on a single line within the '
                                             'cartouche. Supporting copy: humanist sans-serif, light, both scripts.',
                               'design_axis': 'Vector-illustration-led / engraved-field-led — a built concentric '
                                              'contour drawing carries the full lid surface; it is the first and '
                                              'dominant event.',
                               'prompt_seed': 'A shallow matte round pressed-powder compact under warm golden raking '
                                              'light, on a soft sand linen surface. The entire lid face is covered '
                                              'in fine concentric oval contour lines radiating from an off-center '
                                              'point — an engraved topographic field. A clean cream cartouche in the '
                                              'lower third holds the bilingual FOCUS name in equal English serif and '
                                              'Arabic Naskh, rose gold border. Rose gold foil BBROSE lockup at top. '
                                              'Artisanal, precise, quietly luxury.',
                               'color_system': 'CS-002 Nude Warm: Soft Sand (#F0DECB) ground, Warm Nude (#E8C9B3) '
                                               'for engraved lines at hairline weight, Cocoa Rose (#7A4A42) for type '
                                               'inside cartouche, Rose Gold foil on BBROSE lockup and cartouche '
                                               'border rule.',
                               'direction_id': 'd2',
                               'subject_story': "Pressed powder as a sculpted pan: the compact's pressed surface has "
                                                'concentric rings and micro-texture. The engraved contour field on '
                                                "the lid directly mirrors a pressed powder cake's circular geometry "
                                                '— specific, not decorative filler.',
                               'emotional_tone': 'Precise, artisanal, quietly luxurious — a compact that signals '
                                                 'craft and intention at shelf distance.',
                               'focal_hierarchy': 'Eye enters at the engraved field (texture draws the whole lid), '
                                                  'then focuses on the cartouche with the bilingual name, then reads '
                                                  'the BBROSE lockup above.',
                               'graphic_elements': 'Forty to sixty concentric oval contour lines, hairline weight, '
                                                   'spaced 1–1.5 pt apart, radiating from an off-center point — '
                                                   'built as individual Bézier ellipses or offset paths. Cartouche: '
                                                   'a rounded-rectangle vector shape in Warm Cream at 100% opacity '
                                                   'cutting through the field. Hairline rose-gold border on '
                                                   'cartouche.',
                               'hierarchy_family': 'MOTIF_FIRST',
                               'imagery_approach': 'Concept render: compact lit with a low raking light so the '
                                                   'engraved contour lines cast micro-shadows and read as tactile '
                                                   'relief. The field is photographed in warm golden-hour diffuse '
                                                   'light. Printed decoration is 100% vector linework — no '
                                                   'photographic fill.',
                               'layout_structure': 'Lid surface: a dense engraved concentric-oval field fills the '
                                                   'entire lid, radiating from an off-center focal point. BBROSE '
                                                   'lockup in rose gold foil floats above the field at upper center. '
                                                   "'FOCUS' in English and Arabic, both in tight compact serif, is "
                                                   'set inside a clean cream relief panel cut into the lower third '
                                                   'of the field — the panel reads as a debossed cartouche. Shade '
                                                   'name in the narrowest band at the very base.',
                               'concept_statement': 'A built engraved-field surface: the entire lid is covered with '
                                                    'a finely drawn concentric contour field — like a topographic '
                                                    'map of a powder pan — that creates depth and tactility through '
                                                    'linework alone. The motif IS the design; type and logo arrive '
                                                    'above it as a second event.',
                               'originality_notes': 'Concentric contour field is a new motif for BBROSE — not drawn '
                                                    'from any past compact dieline. Cartouche bilingual treatment is '
                                                    'evolved from classical label craft, not from any specific '
                                                    'reference design.',
                               'product_target_fit': 'High: the engraved concentric field is uniquely referential to '
                                                     "a pressed powder pan's milled surface. The cartouche gives "
                                                     'equal bilateral typographic space to both scripts.',
                               'prohibited_choices': ['Do not use photographic or raster texture for the engraved '
                                                      'line field.',
                                                      'Do not substitute a butterfly or sunburst for the concentric '
                                                      'field.',
                                                      'Do not demote the Arabic name to a smaller sub-label inside '
                                                      'the cartouche.',
                                                      'Do not add illustrative mascots or kawaii elements.'],
                               'material_finish_direction': 'Matte soft-touch PET lid (ML-HC-001) so engraved lines '
                                                            'feel drawn-on rather than reflected. Body in same matte '
                                                            'finish. Rose gold hot-foil on BBROSE lockup. Blind '
                                                            'emboss or deboss on cartouche panel for tactile '
                                                            'contrast. Engraved lines may be printed in a slightly '
                                                            'lighter ink than ground or achieved via subtle '
                                                            'gloss-on-matte varnish lines.',
                               'native_reconstruction_plan': 'PRINTED DECORATION: (1) Engraved field: forty to sixty '
                                                             'individual Bézier ellipse paths, each stroked at '
                                                             '0.25–0.5 pt in Warm Nude ink, built as offset path '
                                                             'series from a central anchor — no raster. (2) '
                                                             'Cartouche: a single rounded-rectangle vector path, '
                                                             'filled Warm Cream, with a 0.5 pt Rose Gold stroke '
                                                             'border. (3) Live type: BBROSE lockup fixed vector '
                                                             'artwork in Rose Gold foil; FOCUS in compact serif '
                                                             'OpenType, Arabic name in Naskh/Kufi OpenType Arabic — '
                                                             'both live inside cartouche. Claims and shade in '
                                                             'humanist sans, live. (4) Finish masks: foil mask = '
                                                             'BBROSE lockup + cartouche border paths; blind emboss '
                                                             'mask = cartouche outline path; optional gloss-on-matte '
                                                             'varnish mask = union of all ellipse paths. (5) '
                                                             'Concept-render-only: raking light shadows, tactile '
                                                             'surface feel — photography/3D only. (6) Confirmation: '
                                                             'zero decorative rasters in printed decoration.',
                               'target_structural_guidance': 'Engraved field fills the full lid face. Cartouche '
                                                             'occupies a wide horizontal band in the lower third of '
                                                             'the lid. Body band carries claims and shade name in '
                                                             'both scripts. Closure rim in rose gold or matte cocoa '
                                                             'rose.'},
                              {'name': 'Radiance Panel',
                               'risks': 'Foil laminate on a curved compact lid requires registration precision — the '
                                        'arc boundary line must be engineered with the production supplier before '
                                        'artwork is locked. Deep Rose ground under foil may require a specific ink '
                                        'sequence.',
                               'typography': "English 'FOCUS': wide-tracked elegant sans-serif, large, Deep Rose ink "
                                             'on cream. Arabic name: modernist Kufi or geometric Arabic display, '
                                             'same tracked scale, same Deep Rose — the two names run as a bilingual '
                                             'pair on one composed line or in mirrored stacking. Supporting copy: '
                                             'humanist sans, both scripts, small, Deep Rose.',
                               'design_axis': 'Material/structural-led — a rose gold foil panel angled across the '
                                              'upper lid, in high contrast with a warm cream matte lower zone, is '
                                              'the shelf-scale read before any type or motif.',
                               'prompt_seed': 'A shallow round pressed-powder compact on a warm cream silk surface, '
                                              'warm studio light at a slight angle. The lid is divided by a graceful '
                                              'arc into an upper deep-rose rose-gold hot-foil zone scattered with '
                                              'micro-sparkle vector particles and a pearl BBROSE lockup, and a lower '
                                              'warm-cream matte zone carrying a large bilingual FOCUS name in equal '
                                              'English and Arabic. Material contrast dominates the shelf read. '
                                              'Confident, modern, luxury.',
                               'color_system': 'CS-001 Blush Core extended: Deep Rose (#8B3A52) as the foil zone '
                                               'ground, Rose Gold metallic foil laminate over that zone, Warm Cream '
                                               '(#FAF3EC) as matte zone ground, Deep Rose for English type, a '
                                               'warm-cream ink for Arabic name for maximum contrast on the cream '
                                               'ground. Pearl white for BBROSE lockup in foil zone.',
                               'direction_id': 'd3',
                               'subject_story': 'Pressed powder as a composed two-tone finishing gesture — the split '
                                                'panel mirrors the act of pressing a powder puff: one half the '
                                                'pigment, one half the finish. A radiating micro-sparkle particle '
                                                'field (vector dots) in the foil zone evokes illuminating powder '
                                                'particles catching light.',
                               'emotional_tone': 'Confident, modern, luxury editorial — a compact that reads as a '
                                                 'premium accessory before it reads as a cosmetic.',
                               'focal_hierarchy': 'Eye reads the foil-versus-matte material split first (shelf '
                                                  'read), then the BBROSE lockup in the foil zone, then the large '
                                                  'bilingual FOCUS name in the cream zone.',
                               'graphic_elements': 'The diagonal / arc boundary line between zones, executed as a '
                                                   'crisp Bézier path with a rose gold foil stroke. Micro-sparkle '
                                                   'field in foil zone: one hundred to one hundred fifty small '
                                                   'vector ellipses, varying slightly in scale, in a gradient rose '
                                                   'gold to pale blush, scattered asymmetrically. No other motifs — '
                                                   'material contrast does the work.',
                               'hierarchy_family': 'MATERIAL_FIRST',
                               'imagery_approach': 'Concept render: compact photographed at a slight angle in warm '
                                                   'studio light so the foil zone flashes and the matte zone absorbs '
                                                   'light — maximum material contrast visible in one shot. Printed '
                                                   'decoration is 100% native vector — no photographic fill.',
                               'layout_structure': 'Lid surface: a diagonal or gentle arc divides the lid into an '
                                                   'upper deep-rose foil zone (roughly the upper two-fifths) and a '
                                                   'lower warm-cream matte zone (lower three-fifths). BBROSE lockup '
                                                   "in pearl white sits in the foil zone, upper left. 'FOCUS' in "
                                                   'English and Arabic, equal weight, large, centered in the cream '
                                                   'zone. Micro-sparkle particle field (vector ellipses) scattered '
                                                   'across the foil zone. Shade name in the smallest type at the '
                                                   'very base of the cream zone.',
                               'concept_statement': 'The lid is divided into two distinct material zones by a bold '
                                                    'angled foil panel: the upper zone is a deep rose satin finish '
                                                    'carrying the BBROSE lockup in pearl; the lower zone is warm '
                                                    'cream with the bilingual name set large. The material boundary '
                                                    'IS the design — finish contrast at shelf scale, before type or '
                                                    'motif is read.',
                               'originality_notes': 'The angled foil-split composition is new to this product line — '
                                                    'no past BBROSE face powder reference uses a material-zone split '
                                                    'as the primary design event. The particle field is abstract, '
                                                    'not a photograph of glitter.',
                               'product_target_fit': "High: the two-tone split evokes the pressed-powder compact's "
                                                     'lid-and-pan duality; the foil zone expresses illuminating '
                                                     'powder particles; the bilingual name is given the full lower '
                                                     'zone at equal script weight.',
                               'prohibited_choices': ['Do not use a symmetrical top-band that mirrors the Super Stay '
                                                      'badge zone from FB3093.',
                                                      'Do not render sparkle particles as a raster photograph of '
                                                      'glitter.',
                                                      'Do not place the Arabic name below the English as a subtitle '
                                                      'or sub-brand label.',
                                                      'Do not fill the foil zone with a photographic or illustrative '
                                                      'field.'],
                               'material_finish_direction': 'Rose gold hot-foil laminate on the upper panel zone. '
                                                            'Matte soft-touch finish on the lower cream zone '
                                                            '(ML-HC-001 base). The boundary line receives a separate '
                                                            'foil stroke. BBROSE lockup in pearl foil variant within '
                                                            'the rose-gold field. Body in warm cream matte, closure '
                                                            'in rose gold.',
                               'native_reconstruction_plan': 'PRINTED DECORATION: (1) Zone construction: two filled '
                                                             'vector shapes — upper Deep Rose (#8B3A52) path and '
                                                             'lower Warm Cream (#FAF3EC) path — whose shared edge is '
                                                             'a single Bézier arc, together filling the lid face. '
                                                             '(2) Foil mask: the upper zone shape output as a '
                                                             'separate foil channel; BBROSE lockup pearl variant '
                                                             'output as a second foil channel within that zone. (3) '
                                                             'Boundary stroke: 1 pt Bézier path along the arc, rose '
                                                             'gold foil stroke, separate channel. (4) Particle '
                                                             'field: one hundred to one hundred fifty vector '
                                                             'ellipses, each a solid rose-gold or pale blush fill, '
                                                             'scattered via pattern or manual placement — no raster. '
                                                             '(5) Live type: FOCUS in wide-tracked sans OpenType, '
                                                             'Arabic name in Kufi/geometric Arabic OpenType — both '
                                                             'live in cream zone, Deep Rose ink. BBROSE lockup fixed '
                                                             'vector artwork, pearl foil. Supporting copy humanist '
                                                             'sans, live. (6) Finish masks: matte soft-touch '
                                                             'laminate over lower zone; hot-foil laminate over upper '
                                                             'zone shape. (7) Concept-render-only: foil flash '
                                                             'photography, light direction — photography/3D only. '
                                                             '(8) Confirmation: zero decorative rasters in printed '
                                                             'decoration.',
                               'target_structural_guidance': 'The split occupies the lid face only. The body band is '
                                                             'warm cream matte with claims and shade name in both '
                                                             'scripts. Closure rim in rose gold. The arc boundary '
                                                             'line may run across the lid face at roughly forty-five '
                                                             'degrees or as a gentle convex arc — proportion '
                                                             'confirmed by structural review.'}]},
              {'attempt': 2,
               'codes': ['TYPOGRAPHY_NOT_DISTINCT'],
               'design_intent': {'hierarchy': 'Brand name (BBROSE lockup) anchors trust; product name FOCUS commands '
                                              'the primary read zone in both English and Arabic with equal weight; '
                                              'claims and shade name occupy a secondary band; regulatory copy fills '
                                              'remaining surface area legibly.',
                                 'confidence': 'HIGH',
                                 'composition': 'The compact lid is the hero surface. A clear horizontal structure: '
                                                'brand lockup in the upper register, product name in dual-language '
                                                'symmetry occupying the center, a powder-veil motif bleeding '
                                                'edge-to-edge beneath or behind the type. Closure and body colour '
                                                'reinforce the finish language.',
                                 'focal_point': 'The powder-veil motif — an abstract field expressing finely milled '
                                                'silk particles, translucent layers or a composed micro-radiance — '
                                                'is the subject anchor. It must be specific to pressed powder, not a '
                                                'generic floral or geometric filler.',
                                 'color_strategy': 'Draw from CS-001 Blush Core or CS-002 Nude Warm, chosen per '
                                                   'direction. Rose gold metallic as a detail finish on logo and '
                                                   'accent lines. No neon, no cold grey, no budget-mass colour '
                                                   'flags.',
                                 'motif_strategy': 'The hero motif must express pressed powder: silkiness, '
                                                   'micro-particle veil, layered translucence, or a radial bloom of '
                                                   'fine pigment. Rendered as native vector — contour lines, '
                                                   'translucent gradient veils, particle fields, soft radial strokes '
                                                   '— never a photographic fill. Each direction uses a distinct '
                                                   'motif family from the approved set.',
                                 'imagery_strategy': 'Concept render uses clean studio photography of the physical '
                                                     'compact (warm diffuse light, silk surface, rose gold '
                                                     'reflection). The printed decoration is 100% native-vector: no '
                                                     'photographic field on the container surface.',
                                 'visual_objective': 'Design the Focus Pressed Powder compact container — its '
                                                     'applied label zones, body colour and closure finish — as a '
                                                     'studio packshot. The container must communicate a composed, '
                                                     'skin-finished softness: the subject story is pressed powder '
                                                     'itself — silkiness, weightless coverage, the veil of finely '
                                                     'milled pigment suspended in air. Every surface decision must '
                                                     'make the pack feel like a finished face.',
                                 'forbidden_choices': ['Photographic fields as printed decoration on the container '
                                                       'surface.',
                                                       'Neon, cold grey, gender-neutral-tech palettes.',
                                                       'Kawaii cartoon mascots or illustrated characters.',
                                                       'Copying any historical BBROSE dieline layout composition as '
                                                       'a template.',
                                                       'Raster textures required for the design identity.'],
                                 'source_references': ['CS-001 Blush Core — canonical palette and rose gold metallic '
                                                       'role.',
                                                       'CS-002 Nude Warm — alternative warm nude palette option.',
                                                       'ML-001 Glossy Acrylic — lid finish option.',
                                                       'ML-HC-001 Matte Soft Touch PET — body finish option.',
                                                       'AL-001 Soft Luxury — aesthetic and lighting language for '
                                                       'concept render.'],
                                 'typography_strategy': 'Three distinct type families across the three directions: '
                                                        '(d1) high-contrast didone serif; (d2) condensed geometric '
                                                        'sans paired with structured Naskh; (d3) wide-tracked '
                                                        'humanist sans paired with modernist Kufi. Supporting body '
                                                        'copy in legible humanist sans in both scripts across all '
                                                        'directions. Shade name set in a contrasting light-weight '
                                                        'register.',
                                 'unresolved_questions': ['Confirm final Arabic product name translation and '
                                                          'calligraphic style approval.',
                                                          'Confirm whether lid surface is acrylic gloss or matte PET '
                                                          'before spot UV planning.',
                                                          'Shade range count: how many SKU colourways must the '
                                                          'system accommodate?',
                                                          'Confirm regulatory copy language requirements per '
                                                          'territory (Arabic/English split).'],
                                 'audience_interpretation': 'Middle-Eastern beauty consumers in Jordan, Syria, '
                                                            'Palestine, Lebanon and Tunisia who read Arabic as a '
                                                            'primary script. The pack must treat Arabic and English '
                                                            'with equal typographic authority — not a hierarchy '
                                                            'where Arabic is a footnote. Buyers expect a premium, '
                                                            'feminine, shelf-credible compact that feels composed '
                                                            'and edited rather than playful or loud.',
                                 'originality_constraints': ['Do not copy the kawaii mascot or cartoon character '
                                                             'language from BP6003 or FB2056.',
                                                             'Do not reproduce the sunburst ray pattern from FB5812.',
                                                             'Do not reproduce the starburst badge composition from '
                                                             'FB3093 Super Stay.',
                                                             'Do not use a bold stacked all-caps powder name layout '
                                                             'that directly echoes SF-2049 Loose Powder.'],
                                 'material_finish_direction': 'Matte soft-touch body with spot UV or gloss varnish '
                                                              'over the motif zone for a tactile finish contrast. '
                                                              'Rose gold foil on BBROSE lockup and key accent '
                                                              'strokes. Options per direction include full gloss '
                                                              'acrylic lid, matte PET body, or pearl-white satin '
                                                              'finish.',
                                 'target_structural_guidance': 'This is a PRODUCT CONTAINER design — a shallow round '
                                                               'pressed-powder compact (lid plus body). Design the '
                                                               'lid label, body band and closure finish. Do not '
                                                               'design a folding carton or dieline. The compact is '
                                                               'approximately 170.5 mm wide, 18 mm deep and 122.5 mm '
                                                               'tall in its shelved orientation; the lid face is the '
                                                               'dominant design surface.'},
               'directions': [{'name': 'Silk Veil',
                               'risks': 'Ribbon arcs must be geometrically resolved to avoid looking generic. Arabic '
                                        'and English type sizing requires careful optical calibration — a type '
                                        'specialist review is advised before final art.',
                               'typography': "English 'FOCUS': high-contrast didone serif, large, tracked wide, Deep "
                                             'Rose ink. Arabic name: calligraphic display Arabic (Thuluth-style), '
                                             'same optical size, same Deep Rose. Supporting copy and shade name: '
                                             'humanist sans-serif, light weight, both scripts. No condensed sans or '
                                             'geometric sans used in this direction.',
                               'design_axis': 'Typography-led — the dual-language FOCUS name in large display type '
                                              'is the first event the eye reads; the veil motif is the field it '
                                              'commands.',
                               'prompt_seed': 'A shallow round pressed-powder compact on a warm blush silk surface, '
                                              'warm diffuse studio light. The gloss lid reveals layered translucent '
                                              'ribbon arcs in blush and pale tones — abstract powder-sweep strokes — '
                                              'behind a large equal-weight bilingual FOCUS name in deep rose didone '
                                              'and calligraphic Arabic. Rose gold foil BBROSE lockup at top, shade '
                                              'name at base. Composed, editorial, feminine luxury.',
                               'color_system': 'CS-001 Blush Core: Warm Cream (#FAF3EC) body, Blush (#F2C4CE) '
                                               'primary veil gradient, Pale Petal (#F7DDE3) secondary ribbon layer, '
                                               'Deep Rose (#8B3A52) for type, Rose Gold foil on BBROSE lockup and '
                                               'hairline rule.',
                               'direction_id': 'd1',
                               'subject_story': 'Pressed powder as a sheer, silky veil. The decoration is built '
                                                'entirely from layered translucent Bézier ribbons — abstract '
                                                'powder-sweep arcs — that mimic the trail of a brush through fine '
                                                'pigment. The motif is specific: it cannot be mistaken for water, '
                                                'oil or floral.',
                               'emotional_tone': 'Composed, editorial, quietly confident — a face that is finished '
                                                 'and ready.',
                               'focal_hierarchy': 'Eye enters at the large bilingual FOCUS name, drops through the '
                                                  'veil field, lands on the BBROSE lockup above and the shade name '
                                                  'below.',
                               'graphic_elements': 'Three to five overlapping Bézier ribbon arcs in translucent '
                                                   'Blush and Pale Petal gradients — narrow at entry, widening — '
                                                   'expressing a powder-brush sweep. Particle field of micro-dots at '
                                                   'ribbon termination points. Rose-gold hairline rules at base and '
                                                   'beneath lockup. Motif family: LIQUID.',
                               'hierarchy_family': 'NAME_FIRST',
                               'imagery_approach': 'Concept render: the compact photographed on a warm blush silk '
                                                   'surface under diffuse studio light; the gloss lid reveals the '
                                                   'layered veil field beneath. Printed decoration is 100% vector — '
                                                   'no photographic element on the container surface.',
                               'layout_structure': 'Lid surface: BBROSE lockup small, upper center. Below it, '
                                                   "'FOCUS' in large English didone serif stacked above its Arabic "
                                                   'equivalent at equal optical weight, both center-aligned. The '
                                                   'powder-veil ribbon field bleeds behind and below the type to the '
                                                   'lower edge. A narrow rose-gold hairline rule separates the name '
                                                   'zone from a slim shade-name band at the base.',
                               'concept_statement': 'The lid is a study in pressed-powder silence: a wide '
                                                    'translucent vector-veil field — flowing Bézier ribbons in '
                                                    'layered blush gradients — reads like the moment fine powder is '
                                                    'swept across skin. Type is the event that cuts through the '
                                                    'softness, large and composed.',
                               'originality_notes': 'Ribbon arcs are abstract powder-sweeps, not petals, not liquid '
                                                    'water. The bilingual name stacking is a new composition, not '
                                                    'echoing any prior BBROSE face powder layout.',
                               'product_target_fit': 'High: the ribbon-veil motif is specific to pressed powder; the '
                                                     "bilingual name hierarchy directly answers the brief's "
                                                     'equal-weight Arabic requirement.',
                               'prohibited_choices': ['Do not render the ribbons as photographic silk or raster '
                                                      'texture.',
                                                      'Do not position the Arabic name as a smaller subtitle below '
                                                      'the English.',
                                                      'Do not use a sunburst or ray pattern — that is FB5812 '
                                                      'territory.',
                                                      'Do not add kawaii characters or playful badge shapes.'],
                               'material_finish_direction': 'Gloss acrylic lid (ML-001) so the veil reads with '
                                                            'depth. Matte soft-touch body. Rose gold hot-foil stamp '
                                                            'on BBROSE lockup. Spot UV gloss varnish over the ribbon '
                                                            'arcs for tactile contrast against the matte inner band.',
                               'native_reconstruction_plan': 'PRINTED DECORATION: (1) Live type: BBROSE lockup as '
                                                             'fixed vector artwork, rose-gold foil variant; FOCUS in '
                                                             'didone serif OpenType, Arabic name in Thuluth-style '
                                                             'calligraphic OpenType Arabic — both live; supporting '
                                                             'copy in humanist sans, live. (2) Veil motif: three to '
                                                             'five Bézier path ribbons, each a gradient mesh from '
                                                             'Blush to Pale Petal at 40–70% opacity, stacked on a '
                                                             'Warm Cream ground — no raster. (3) Particle field: '
                                                             'small vector ellipses, uniform radius, scattered at '
                                                             'ribbon ends via step-repeat pattern — no raster. (4) '
                                                             'Hairline rules: 0.25 pt vector strokes in Rose Gold '
                                                             'swatch. (5) Finish masks: spot UV shape = union of all '
                                                             'ribbon paths, output as separate vector layer; foil '
                                                             'mask = BBROSE lockup outline path. (6) '
                                                             'Concept-render-only: gloss lid reflections, silk '
                                                             'surface, ambient warm light — photography or 3D render '
                                                             'only, never printed. (7) Confirmation: zero decorative '
                                                             'rasters required in the printed decoration.',
                               'target_structural_guidance': 'Design the compact lid (dominant circular face), the '
                                                             'narrow body band, and the closure rim. The lid carries '
                                                             'all decorative artwork. The body band carries shade '
                                                             'name and four claims in both scripts. Closure rim in '
                                                             'rose gold finish.'},
                              {'name': 'Poudre Engraved',
                               'risks': 'Dense linework must be tested at production scale — lines may close up if '
                                        'printed at hairline weights on matte substrate. Recommend a press proof '
                                        'before finalising line spacing.',
                               'typography': "English 'FOCUS': condensed geometric sans-serif (narrow, tight "
                                             'tracking, strong vertical stress), Cocoa Rose. Arabic name: structured '
                                             'modernist Naskh, matched to the same condensed geometric optical '
                                             'weight, Cocoa Rose — set alongside the English on one line inside the '
                                             'cartouche. Supporting copy: condensed geometric sans, light, both '
                                             'scripts. No didone serif or script faces used in this direction.',
                               'design_axis': 'Vector-illustration-led / engraved-field-led — a built concentric '
                                              'contour drawing carries the full lid surface; it is the first and '
                                              'dominant event.',
                               'prompt_seed': 'A shallow matte round pressed-powder compact under warm raking '
                                              'side-light on a soft sand linen surface. The entire lid face is '
                                              'covered in fine concentric oval contour lines radiating from an '
                                              'off-center point. A clean cream cartouche in the lower third holds '
                                              'the bilingual FOCUS name in equal-weight condensed geometric sans '
                                              'English and modernist Naskh Arabic, rose gold border. Rose gold foil '
                                              'BBROSE lockup at top. Artisanal, precise, quietly luxurious.',
                               'color_system': 'CS-002 Nude Warm: Soft Sand (#F0DECB) ground, Warm Nude (#E8C9B3) '
                                               'for engraved lines at hairline weight, Cocoa Rose (#7A4A42) for type '
                                               'inside cartouche, Rose Gold foil on BBROSE lockup and cartouche '
                                               'border rule.',
                               'direction_id': 'd2',
                               'subject_story': "Pressed powder as a sculpted pan: the compact's pressed surface has "
                                                'concentric rings. The engraved contour field on the lid directly '
                                                "mirrors a pressed powder cake's circular geometry — material and "
                                                'specific, not decorative filler.',
                               'emotional_tone': 'Precise, artisanal, quietly luxurious — a compact that signals '
                                                 'craft and intention at shelf distance.',
                               'focal_hierarchy': 'Eye enters at the engraved field (texture draws the whole lid), '
                                                  'then focuses on the cartouche with the bilingual name, then reads '
                                                  'the BBROSE lockup above.',
                               'graphic_elements': 'Forty to sixty concentric oval contour lines, hairline weight, '
                                                   'spaced 1–1.5 pt apart, radiating from an off-center point — '
                                                   'built as individual Bézier ellipses. Cartouche: a '
                                                   'rounded-rectangle vector shape in Warm Cream at 100% opacity '
                                                   'cutting through the field. Hairline rose-gold border on '
                                                   'cartouche. Motif family: LINEAR_ENGRAVED.',
                               'hierarchy_family': 'MOTIF_FIRST',
                               'imagery_approach': 'Concept render: a render photograph of the compact under warm '
                                                   'raking side-light so the contour lines read as tactile relief on '
                                                   'the matte lid. Printed decoration is 100% vector linework — no '
                                                   'photographic fill on any container surface.',
                               'layout_structure': 'Lid surface: a dense engraved concentric-oval field fills the '
                                                   'entire lid, radiating from an off-center focal point. BBROSE '
                                                   'lockup in rose gold foil floats above the field at upper center. '
                                                   "'FOCUS' in English and Arabic, set in condensed geometric sans, "
                                                   'is placed inside a clean cream relief cartouche cut into the '
                                                   'lower third of the field. Shade name in the narrowest band at '
                                                   'the very base.',
                               'concept_statement': 'A built engraved-field surface: the entire lid is covered with '
                                                    'finely drawn concentric contour lines — like a topographic map '
                                                    'of a powder pan — creating depth and tactility through linework '
                                                    'alone. The field IS the design; type and logo arrive above it '
                                                    'as a second event.',
                               'originality_notes': 'Concentric contour field is new for BBROSE — not drawn from any '
                                                    'past compact dieline. Cartouche bilingual treatment evolved '
                                                    'from classical label craft, not from any specific reference '
                                                    'design.',
                               'product_target_fit': 'High: the concentric contour field is uniquely referential to '
                                                     "a pressed powder pan's milled surface. The cartouche gives "
                                                     'equal bilateral typographic space to both scripts.',
                               'prohibited_choices': ['Do not use photographic or raster texture for the engraved '
                                                      'line field.',
                                                      'Do not substitute a butterfly or sunburst for the concentric '
                                                      'contour field.',
                                                      'Do not demote the Arabic name to a smaller sub-label inside '
                                                      'the cartouche.',
                                                      'Do not add illustrative mascots or kawaii elements.'],
                               'material_finish_direction': 'Matte soft-touch PET lid (ML-HC-001) so engraved lines '
                                                            'feel drawn-on. Body in same matte finish. Rose gold '
                                                            'hot-foil on BBROSE lockup. Blind emboss on cartouche '
                                                            'panel. Engraved lines printed in a slightly lighter ink '
                                                            'than ground, or via gloss-on-matte varnish lines.',
                               'native_reconstruction_plan': 'PRINTED DECORATION: (1) Engraved field: forty to sixty '
                                                             'individual Bézier ellipse paths, each stroked at '
                                                             '0.25–0.5 pt in Warm Nude ink, built as offset path '
                                                             'series from a central anchor — no raster. (2) '
                                                             'Cartouche: a single rounded-rectangle vector path, '
                                                             'filled Warm Cream, with a 0.5 pt Rose Gold stroke '
                                                             'border. (3) Live type: BBROSE lockup fixed vector '
                                                             'artwork in Rose Gold foil variant; FOCUS in condensed '
                                                             'geometric sans OpenType; Arabic name in modernist '
                                                             'Naskh OpenType Arabic — both live inside cartouche. '
                                                             'Claims and shade name in condensed geometric sans, '
                                                             'live. (4) Finish masks: foil mask = BBROSE lockup + '
                                                             'cartouche border paths as vector outlines; blind '
                                                             'emboss mask = cartouche outline path; optional '
                                                             'gloss-on-matte varnish mask = union of all ellipse '
                                                             'paths. (5) Concept-render-only: raking light '
                                                             'micro-shadows — photography or 3D render only, never '
                                                             'printed. (6) Confirmation: zero decorative rasters in '
                                                             'printed decoration.',
                               'target_structural_guidance': 'Engraved field fills the full lid face. Cartouche '
                                                             'occupies a wide horizontal band in the lower third of '
                                                             'the lid. Body band carries claims and shade name in '
                                                             'both scripts. Closure rim in rose gold or matte cocoa '
                                                             'rose.'},
                              {'name': 'Radiance Panel',
                               'risks': 'Rose gold foil laminate over a large zone requires tight registration on '
                                        'the Bézier boundary arc. Recommend a foil press proof before finalising the '
                                        'arc angle and stroke weight.',
                               'typography': "English 'FOCUS': wide-tracked humanist sans-serif (open aperture, "
                                             'moderate x-height, generous letter-spacing), large, Deep Rose ink on '
                                             'cream. Arabic name: modernist Kufi geometric display Arabic, same '
                                             'wide-tracked scale, Deep Rose — bilingual pair on one composed line. '
                                             'Supporting copy: humanist sans, both scripts, small. No didone serif '
                                             'or condensed geometric sans used in this direction.',
                               'design_axis': 'Material/structural-led — a rose gold foil panel angled across the '
                                              'upper lid, in high contrast with a warm cream matte lower zone, is '
                                              'the shelf-scale read before any type or motif.',
                               'prompt_seed': 'A shallow round pressed-powder compact at a slight angle in warm '
                                              'studio light, foil upper panel flashing rose gold against a matte '
                                              'warm cream lower panel. The foil zone is scattered with tiny '
                                              'geometric hexagonal facets in gradient rose gold. Pearl BBROSE lockup '
                                              'upper left in the foil zone; large bilingual FOCUS in wide-tracked '
                                              'humanist sans and Kufi Arabic centered in the cream zone. Bold '
                                              'material contrast, modern luxury editorial.',
                               'color_system': 'CS-001 Blush Core extended: Deep Rose (#8B3A52) as foil zone ground, '
                                               'Rose Gold metallic foil laminate over that zone, Warm Cream '
                                               '(#FAF3EC) as matte zone ground, Deep Rose for English type, Deep '
                                               'Rose for Arabic name on cream ground. Pearl white for BBROSE lockup '
                                               'in foil zone.',
                               'direction_id': 'd3',
                               'subject_story': 'Pressed powder as a composed two-tone finishing gesture — the split '
                                                'panel mirrors pressing a powder puff: one half pigment depth, one '
                                                'half luminous finish. A geometric particle field of vector '
                                                'hexagonal micro-facets in the foil zone evokes illuminating powder '
                                                'particles catching light, rendered as a GEOMETRIC_ABSTRACT motif.',
                               'emotional_tone': 'Confident, modern, luxury editorial — a compact that reads as a '
                                                 'premium accessory before it reads as a cosmetic.',
                               'focal_hierarchy': 'Eye reads the foil-versus-matte material split first (shelf '
                                                  'read), then the BBROSE lockup in the foil zone, then the large '
                                                  'bilingual FOCUS name in the cream zone.',
                               'graphic_elements': 'The diagonal arc boundary line between zones: a crisp Bézier '
                                                   'path with a rose gold foil stroke. Geometric micro-facet field '
                                                   'in foil zone: one hundred to one hundred fifty small vector '
                                                   'regular hexagons, varying slightly in scale, in a gradient rose '
                                                   'gold to pale blush, scattered asymmetrically across the foil '
                                                   'zone. Motif family: GEOMETRIC_ABSTRACT. No other drawn motifs — '
                                                   'material contrast carries the surface.',
                               'hierarchy_family': 'MATERIAL_FIRST',
                               'imagery_approach': 'Concept render: a render photograph of the compact at a slight '
                                                   'angle in warm studio light so the foil zone flashes and the '
                                                   'matte zone absorbs — maximum material contrast visible in one '
                                                   'shot. Printed decoration is 100% native vector — no photographic '
                                                   'fill on any container surface.',
                               'layout_structure': 'Lid surface: a diagonal Bézier-edge arc divides the lid into an '
                                                   'upper deep-rose foil zone (roughly upper two-fifths) and a lower '
                                                   'warm-cream matte zone (lower three-fifths). BBROSE lockup in '
                                                   "pearl white sits in the foil zone, upper left. 'FOCUS' in "
                                                   'English and Arabic, equal weight, large, centered in the cream '
                                                   'zone. Geometric micro-facet field scattered across the foil '
                                                   'zone. Shade name in the smallest type at the very base of the '
                                                   'cream zone.',
                               'concept_statement': 'The lid is divided into two distinct material zones by a bold '
                                                    'angled foil boundary: the upper zone is a deep rose satin '
                                                    'finish carrying the BBROSE lockup in pearl; the lower zone is '
                                                    'warm cream matte with the bilingual name set large. The '
                                                    'material contrast IS the shelf read — finish speaks before type '
                                                    'or motif.',
                               'originality_notes': 'Hexagonal micro-facet field is new for BBROSE — drawn from '
                                                    'geometric abstraction, not from botanical or liquid motif '
                                                    'language. The diagonal foil split is a new composition for this '
                                                    'product line.',
                               'product_target_fit': "High: the two-tone split evokes the compact's lid-and-pan "
                                                     'duality; the foil zone and hexagonal facets express '
                                                     'illuminating powder particles; the bilingual name is given the '
                                                     'full lower zone at equal script weight.',
                               'prohibited_choices': ['Do not use a photographic or raster fill in either panel '
                                                      'zone.',
                                                      'Do not substitute the geometric facets with botanical or '
                                                      'liquid vector motifs.',
                                                      'Do not demote the Arabic name to a smaller sub-label below '
                                                      'the English FOCUS.',
                                                      'Do not add kawaii mascots, starburst badges, or sunburst '
                                                      'rays.'],
                               'material_finish_direction': 'Rose gold hot-foil laminate on the upper panel zone. '
                                                            'Matte soft-touch finish on the lower cream zone '
                                                            '(ML-HC-001 base). The boundary arc receives a separate '
                                                            'foil stroke. BBROSE lockup in pearl foil variant within '
                                                            'the rose-gold field. Body in warm cream matte, closure '
                                                            'in rose gold.',
                               'native_reconstruction_plan': 'PRINTED DECORATION: (1) Panel zones: two filled vector '
                                                             'shapes — an upper irregular arc-edged polygon in Deep '
                                                             'Rose and a lower complementary arc-edged polygon in '
                                                             'Warm Cream — together covering the full lid circle, '
                                                             'edges defined by a single Bézier arc path. No raster. '
                                                             '(2) Geometric micro-facet field: one hundred to one '
                                                             'hundred fifty vector regular hexagons (each a closed '
                                                             'six-sided Bézier polygon), scaled 1–3 pt, filled with '
                                                             'gradient swatches from Rose Gold to Pale Blush at '
                                                             '50–80% opacity, placed within the foil zone as a '
                                                             'scatter pattern — no raster. (3) Boundary arc: a '
                                                             'single Bézier stroke path at 1 pt in Rose Gold foil '
                                                             'ink. (4) Live type: BBROSE lockup fixed vector artwork '
                                                             'in pearl foil variant; FOCUS in wide-tracked humanist '
                                                             'sans OpenType; Arabic name in modernist Kufi OpenType '
                                                             'Arabic — both live in cream zone. Supporting copy in '
                                                             'humanist sans, live. (5) Finish masks: foil mask = '
                                                             'upper panel shape + boundary arc path + BBROSE lockup '
                                                             'outline + hexagon union path; matte zone = lower panel '
                                                             'shape. (6) Concept-render-only: foil flash, specular '
                                                             'reflections, angular studio lighting — photography or '
                                                             '3D render only, never printed. (7) Confirmation: zero '
                                                             'decorative rasters required in the printed decoration.',
                               'target_structural_guidance': 'The split panel occupies the lid face only. The body '
                                                             'band is warm cream matte carrying shade name and '
                                                             'claims in both scripts. Closure rim in rose gold. No '
                                                             'split panel extends to the body.'}]}]}
