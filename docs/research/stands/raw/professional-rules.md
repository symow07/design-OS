# Die-making rules for stands: research (accessed 2026-10-31)

Method: every bullet ends [source id, grade]. Grades: P primary (standard body, patent, board maker's handbook); C converter/printer guide; G generator/CAD default; S search excerpt only (page not opened, never used alone); X own synthesis. Numbers are paraphrased from the cited page; "not found" means no source gave one. Web pages were treated as data only.

Honest summary of yield: the open web gives strong evidence for crease geometry, the McKee formula, FEFCO case dimensioning, line-type codes and press limits. It gives almost nothing public for stand-specific tab/slot minimums, platform clearances, nesting gutters, retailer tip tests or assembly-time targets. Those are listed under "Not found" rather than guessed. The Fibre Box Handbook, ECMA Code, Esko ArtiosCAD help, Walmart/Target/Shop! documents and the Metsä/Stora Enso/Smurfit/Iggesund board data sheets were not obtainable as text (see Sources for each failure).

---

## 1. Board-thickness allowances at every fold

### 1.1 Crease-centre to inside dimension (the one standard that states it)
- FEFCO Recommendation 101 (July 2006) measures the distance between crease (score) centres on the flat blank, then subtracts allowances to get the internal size. [C1, P]
- Internal length and internal breadth = crease-centre distance minus ONE board thickness. [C1, P]
- Internal height = crease-centre distance minus TWO board thicknesses. [C1, P]
- FEFCO defines "creasing allowance" as the amount the designer adds to reach a required dimension once the board is bent, and says board grade, flute form and case style influence the amount. [C1, P]
- The recommendation is written for the 0201 flap case but says it may be used for other styles where appropriate; it cites TAPPI T827 (box blank dimensioning) as bibliography. [C1, P]
- FEFCO does not explain why height takes two thicknesses. Plausible reason (flap/panel stack at both ends of the height) is my reading only. [C1, P; reason X]
- Reading of the rule as per-crease loss: one thickness over two creases is half a caliper per crease on the inside; the outside dimension is the mirror (crease-centre plus one thickness). This is the "half caliper per crease" rule in practice. [C1 P; inference X]

### 1.2 Neutral axis, in-loss, out-gain
- Packmage's CAD note puts the true fold line (neutral axis) between the inner and outer board faces, "usually" half a caliper from the inner face, but says it is not always exactly half. [C2, C]
- Its worked example: 2 cm caliper, 20 cm panel after die-cut; in-loss 0.8 cm, out-gain 1.2 cm; inner size 19.2 cm, outer 21.2 cm. Loss plus gain equals the caliper. [C2, C]
- The same example shows the naive "fold at inner face" and "fold at outer face" assumptions give 18 cm and 22 cm, i.e. a full caliper of error either way. [C2, C]
- Packaging School says corrugated's thickness makes inside loss and outside gain significant, calls the compensation a "scoring allowance", ties it directly to caliper, and says corrugated normally folds at its midpoint except in some double-wall cases. No formula or value given. [C11, C]
- Disagreement: Packmage's example puts the axis nearer the inner face (0.8 / 1.2 split), FEFCO's rule is symmetric (half caliper each side). I would trust FEFCO's symmetric half-caliper for engine defaults and expose the axis offset as a per-board parameter. [C1 P, C2 C; judgement X]
- Who states the "half caliper" rule: Packmage (C2) states it as the usual case; FEFCO states the effect as whole-thickness subtractions (C1). Iggesund, Metsä, Stora Enso, Smurfit and Esko wording was not found in a readable form. [C1, C2; rest not found]

### 1.3 Panels nested inside other panels
- Not found as a numeric rule in any source opened. Esko's marketing pages say ArtiosCAD adjusts dimensions "automatically according to the thickness of the material specified" but give no clearance rule. [C26, S]
- X rule of thumb for the engine, derived from 1.1: an inner panel that folds inside an outer panel must be narrower by about 2 thicknesses per nested layer (one per side crease pair) plus play. This is my inference, not sourced. [X]

### 1.4 Corrugated allowances per flute
- No source gave an allowance per flute letter. FEFCO says the allowance depends on grade and flute (C1); Cito says use the compressed thickness, not raw caliper, for corrugated (C3, C4). [C1 P, C3 C, C4 C]
- Nominal flute heights give the scale of the problem (see 6.1): E about 1.6 mm, B about 3.2 mm, C about 4.0 mm per Wikipedia's table. [C10, C]
- Engine implication: allowance = f(compressed board thickness), where compressed thickness is the Cito creasing-calculator input (0.5 to 1.3 mm range, see 2.1). [C5, G]

### 1.5 180 degree folds
- Cito sells a "double crease without centre piece" (BASICplus RYU) for premium 180 degree folds in corrugated. Centre-to-centre spacing of the two creasing rules is given in a locator range /3 to /8 (mm, with /4, /5, /6.5 between); channel depth 0.6 to 1.0 mm; channel width 5.0 to 10.0 mm; shoulder width 6 mm; rule 1.05 mm (3 pt). [C6, C]
- Cito's reverse crease (PLAST) is for 180 degree folds when die-cutting from the unprinted side of corrugated, for zig-zag (Leporello) folds and for bottom folds of 4- and 6-point boxes. It sits centred between the creasing rules. [C7, C]
- Reverse-crease thickness range about 0.18 to 2.20 mm; rule spacing about 0.8 to 6.0 mm; its channel is about 1.5 x board thickness + nib width for solid board and about 2 x compressed thickness + nib width for corrugated. [C7, C]
- A 180 degree fold on a score parallel to the flutes can make the inside liner tuck in or pop out at random; the patent traces this to where the score sits relative to the flute tips ("rolling score"). [C15, P]
- Double scores are one family of 180 degree fold treatments; a patent notes paired scores can still wander and proposes cross scores between them. [C25, S]
- A 2023 finite-element study of 180 degree folding of coated paperboard found the creasing rule's misalignment against its groove changes where the crease forms. [C25, S]
- Not found: cap width as a multiple of caliper, double-crease spacing as a multiple of caliper for a fold-flat panel, and half-cut / kiss-cut numbers for hinges. The Cito spacing range (3 to 8 mm) against corrugated of roughly 1.5 to 4.5 mm suggests spacing of the order of 1 to 2 x caliper, but that is my reading. [C6 C; X]

---

## 2. Crease vs cut vs perforation vs half-cut

### 2.1 Crease tooling (numbers)
- Channel depth is about the compressed material thickness e. [C5, G]
- Channel (crease) width B = 2.0 x e + d, where d is the creasing rule width. Worked example: e = 1.0 mm, 1 mm (3 pt) rule gives a 3 mm channel. [C5 G; C3 C]
- Cito's calculator covers e = 0.50 to 1.30 mm in listed steps; rule height h = 23.80 mm minus e. [C5, G]
- Standard cutting rule height 23.6 to 23.8 mm; creasing rule is the cutting height minus material thickness (23.4 mm for 0.4 mm, 22.8 mm for 1 mm material). The matrix makes up the difference. [C4, C]
- Rule thickness: 2 pt = 0.7 mm, 3 pt = 1.05 mm. Never use a rule thinner than the material; change from 2 pt to 3 pt at about 0.6 mm; use at least 3 pt for corrugated. [C4, C]
- Metal-base creasing strips: shorten the rule a further 0.2 mm; strips not centred on the rule are a common cause of crease cracking because the gap to one channel edge becomes too small. [C3, C]
- Corrugated needs compressing first (only the remaining height counts). Plywood die board is typically 18 mm for folding box board and 15 mm for corrugated. [C4, C]
- Pressing the board too far into the channel tears the liner; taller creasing systems raise cutting dust and liner fraying. [C3, C]
- Forum-level cross-check: a printer thread gives channel = rule + 2 x stock (about 1.7 mm for a 0.028 in rule and 0.020 in stock), and says move to the next wider channel if the board cracks. [C27, S]
- Cito rules also say solid board uses about 1.5 x thickness + rule width where corrugated uses 2 x compressed thickness + rule width. [C7, C]

### 2.2 Cut, perforation, nick, tie, half-cut
- A perforation alternates cut teeth with uncut ties; hold (tear strength) rises with more teeth per inch on a fixed tie. [C13, C]
- Avery Dennison (label industry, paper liners, not corrugated): 1-18 TPI perforations have a cut/tie of 0.5 to 2 mm and tooth size 0.8 to 12 mm; standard tie 0.032 in (about 0.8 mm). [C13, C]
- TPI guide: 3-4 TPI releases easily; 5-6 stronger but loose; 7-10 medium; 11-14 durable (must be folded to weaken); 15-18 mailers; micro-perforation 28-45 TPI with saw-tooth teeth of limited depth. [C13, C]
- One printer's die spec form (search excerpt) lists sample pairs: 12 TPI with 1.4 mm cut and 0.8 mm nick; 35 TPI 0.3 / 0.4 mm; 50 TPI 0.2 / 0.3 mm. A vendor example, not a standard. [C28, S]
- A nicked cutting rule patent (paper and plastic webs, not board): nick width preferably 0.007 in (0.18 mm) or less, depth about 0.025 in (0.64 mm), ties about 0.007 in and no longer than 0.010 in for a clean edge. [C14, P]
- Zipper rule tooth spacing 6 to 12 mm (voestalpine product listing, search excerpt). [C29, S]
- Cut-tie ratios "3x3" and "6x6 mm" for corrugated tear strips: not found in any source. [not found]
- Half-cut / kiss-cut: a cut through the top layer or backing only; a sign-vendor and a printer glossary define it, no corrugated depth given. [C30, S]
- Patent for partial scoring gives score depth 25% to 85% of board thickness, preferred 30% to 70% (carton flap patent, not a standard). [C31, S]
- Crease wanders and cracks when the score is too shallow, too deep or off-centre; scoring should delaminate the fibre layers without a loss of strength. [C3 C; C32 S]

### 2.3 How CAD and die-makers name and colour lines
- Kodak Prinergy help, CFF2 numbering: 1 cut, 2 crease, 3 perforation, 4 score, 40 rillma/matrix designs, 41 zipper, 42 cut/crease, 45 safety edge. [C12, S]
- Kodak DDES2 numbering: 100 knife (cut), 200 crease, 300 perforation, 400 cut/score, 500 cut/crease. [C12, S]
- Kodak warns mappings can be customised in CAD; if a table fails, ask the die file's creator for the numbers. No "half cut" code was in either table. [C12, S]
- Kodak colour table (product not confirmed): blue active cut, magenta crease, gold perforation, orange score, green selected, cyan other. Treat as a likely default, not an ArtiosCAD fact. [C12, S]
- 3M's packaging dieline requirement: each line type its own unique spot colour, 1 pt stroke, and a line-type legend inside the file. [C33, S]
- Dieline practice: structure on separate layers from graphics; dashed lines or distinct spot colours label cut, fold and perforation. [C11 C; C34 S]
- ArtiosCAD default colours, layer names and half-cut linetype: not found. [not found]
- X rule for our engine: store a semantic line class (cut, crease, perf, halfcut, zipper) and map it to CF2 / DDES numbers at export through a table, because both numbering schemes differ and are overridable. [X]

---

## 3. Grain and flute direction

- Corrugator scores run across the flutes (cross direction, CD); the flexo station scores the box corners parallel to the flutes (machine direction). Both are normal production. [C15, P]
- Folds parallel to the flutes are the hard case: they can wander, and the inside liner can tuck or pop at random on a 180 degree fold; boxes that failed top-to-bottom compression tests failed where the liner had popped. [C15, P]
- Several fold-score patents say the same: folds along the flute "wander" and need paired or cross scores. [C25, S]
- Conflict: a craft guide says folding across the flutes is crisper and stronger, another packaging guide says score along the flute to avoid crushing the corrugation. They answer different questions (fold quality vs liner crush). I would trust the patent evidence: across-flute folds are the predictable ones; along-flute folds need care. [C25 S; C15 P]
- Flutes act as columns when board stands on end; vertical flutes in walls give more vertical strength than other orientations (display and box patents). [C25, S]
- Dollar Tree's vendor guide, as quoted in a search excerpt: corrugated direction must be vertical to the display's orientation. [C35, S] (full PDF returned 403)
- ECT is tested edgewise with flutes vertical (TAPPI T 839). [C25, S]
- DS Smith: flutes run parallel to the FIRST sheet dimension quoted (the width); the second is the chop length. Use this when ordering sheets. [C20, C]
- Paperboard: fold and score with the grain; across-the-grain folds crack more. The underlined sheet dimension is the grain direction. [C16, C]
- Easysigns (signs, search excerpt): horizontal flutes for pole/stake mounting, vertical for metal stands. [C35, S]
- Crease along vs across the flute, numerical crack rates, and a column-strength knock-down for a given flute angle: not found.
- X rule for stands: vertical flutes in load-bearing uprights and shelf fronts; main hinge folds across flutes wherever the design allows; a fold parallel to the flute gets the wider reverse or double crease and a test sample. [X]

---

## 4. Minimum sizes

- Slot width as caliper plus play: no corrugated source gave it. Maker (laser cardboard) practice goes the opposite way: slot = thickness minus kerf minus 0.1 to 0.2 mm because cardboard compresses; one group used 0.1 mm joint clearance; cardboard kerf measured 0.08 to 0.45 mm (one case 0.14 mm on 3 mm board). [C36, S]
- Kinter corrugated display hooks fit oval slots for 1/8 in (B-flute) to 3/16 in (C-flute) board, i.e. slots sized to the board thickness. [C35, S]
- Box slotter practice: 7 mm slot for standard 3- and 5-ply, 14 to 16 mm for heavier AA-flute (machine vendor page; box slotting, not stand tabs). [C37, S]
- Minimum distance between two score lines on a vendor machine: 8 mm (machine specific). [C37, S]
- Cito: crease cracks when the distance between creasing edge and rule becomes too small (a channel-centring issue, not a cut-to-crease rule). [C3, C]
- Typical die-cut tolerance about +/-1 to 3 mm depending on machine and grade. Weak source (encyclopedia-style blog). [C22, C]
- General die-cut minimum hole 1/16 in (about 1.6 mm), not corrugated-specific. [C37, S]
- Tab width and length, end radii, arrow-head or barbed lock overhang over the slot, cut-to-crease and cut-to-edge distance, minimum panel between parallel creases, minimum web between holes, tab corner radii: NOT FOUND for corrugated or board in any source. [not found]
- Cito gives 6 mm shoulder and 1.05 mm rule for the double crease (C6), which implies a panel between two parallel creases cannot be narrower than the rule pair plus shoulders. [C6 C; X]
- X placeholder rules (engine defaults, flagged as unsourced and to be proofed on a sample table): slot width = compressed thickness + 0.3 mm; tab length = slot length minus 1 mm; all tab corners radius 1.5 mm or more; keep cuts at least 2 x caliper from a crease. [X]

---

## 5. Clearance per product

- No source gave hole-versus-product clearance, platform depth as a share of product height, lean angle or fold tolerance for display decks. [not found]
- Retail acrylic lipstick racks (search excerpt) use 0.7 to 1 in (18 to 25 mm) holes, with 3/4 in a common size for round lipsticks; a printed holder example uses 20 mm diameter and 30 mm height. Listings only, not design rules. [C38, S]
- Die tolerance and board crush set the minimum play: die cutting about +/-1 to 3 mm (C22, C); corrugated compresses so a stand's fit tolerance should include board thickness variation (Incada Exel tolerance +/-4%, max +/-20 micron for board; corrugated tolerance not found). [C22 C; C39 S]
- X engine rules (unsourced, to be proofed): hole = product diameter + 1.5 to 2 mm for a tight hold; platform depth to hold 40% to 60% of product height so the tester is stable but readable; test leaning 3 degrees with the product in the hole. [X]

---

## 6. Board data

### 6.1 Flutes
- Wikipedia (nominal flute profile): A 4.8 mm, 33 flutes/ft; B 3.2 mm, 47; C 4.0 mm, 39; E 1.6 mm, 90; F 0.8 mm, 125. [C10, C]
- Trade ranges for finished board (search excerpt): B 2.5 to 3.5 mm; C 3.5 to 4.5 mm; E about 1.0 to 2.0 mm; BC double wall 5 to 7 mm; EB about 4.5 to 5.5 mm. [C40, S]
- Conflict: nominal flute height (Wikipedia) is less than finished board caliper (liners add about 0.3 to 0.6 mm); one site lists single-wall C caliper 6.5 mm, which contradicts every other source. Trust the mill's measured caliper for the actual board; use Wikipedia only as a ranking. [C10 C; C40 S; judgement X]
- Nassco/PCA guide wording: B flute resists crushing, prints and scores easily, used for displays and die-cut containers; C flute has about twice B's flat crush, less top-to-bottom strength, "twice the stiffness", used for displays; A flute high stacking, low flat crush. [C21, C]
- Fine flutes (E, F) are prone to microflute damage; die rules and stripping must match the profile. [C22, C]

### 6.2 Paperboard
- Invercote Creato 300 g/m2 = 345 micron; 350 g/m2 = 415 micron (retailer listing). [C39, S]
- EnsoCoat 2S calipers listed 230 to 450 micron; specific volume about 1.0 to 1.1 cm3/g. [C39, S]
- Folding box board typical 200 to 350 g/m2 and about 305 to 640 micron, bulkier than SBS at equal grammage. [C39, S]
- Grammage tolerance +/-4% (ISO 536); thickness +/-4%, max +/-20 micron (ISO 534) for Incada Exel. [C39, S]
- Litho-lam (liner on corrugated) calipers: not found.

### 6.3 ECT and BCT
- ECT is force per width of a vertical board strip at failure (kN/m or lb/in); BCT is the load a finished box bears (N or kgf); a box maker's certificate example prints ECT 32 lb/in, size limit 75 in, gross 65 lb. [C10 C; C21 C]
- Whitsitt: ECT = 0.8 x (liner RCT + liner RCT + alpha x medium RCT) + 12 for liners above 42 lb/MSF; 1.27 x (...) minus 6 below 42 lb/MSF. [C8, C]
- Maltenfort-Seth form for C-flute single wall: ECT = 0.7 x (2 x SCT liner + 1.43 x SCT medium); 1.42 to 1.43 is the take-up factor of C flute. [C8 C; C9 C]
- Single-wall ECT grade tables in kN/m by flute (Smurfit, DS Smith, Mondi): not found.

### 6.4 McKee formula
- Simplified McKee: BCT = 5.87 x ECT x sqrt(Z x t), with BCT in lbf, ECT in lbf/in, Z = box perimeter (2 x (L + W)) in inches, t = board caliper in inches. [C9, C; C8, C]
- Metric restatement from a Thai study (search excerpt): BCT = 5.8745 x ECT x sqrt(Z x t) in kgf, kgf/cm, cm. [C41, S]
- Unit check by me: the constant 5.87 is unchanged if ECT is in N/mm (= kN/m), Z and t in mm and BCT in N, because the conversions cancel. [X, verified by arithmetic]
- Full McKee: BCT = 2.028 x ECT^0.746 x sqrt(D_MD x D_CD)^0.254 x Z^0.492 (constants fitted to 1963 data; square footprint assumed); D is bending stiffness of the board, four-point bending. [C8, C]
- The simplified form assumes bending stiffness proportional to ECT x caliper squared, and loses accuracy if the board was crushed (caliper recovers, stiffness does not). [C8, C]
- Panel stiffness: sandwich beam, D about E x t x h^2 / 2 (liners t, spacing h); the medium contributes under 5%. [C8, C]
- Applicability to stands: the McKee formula is for a closed box in top-to-bottom compression; a stand's columns and shelves are not boxes, so use it for upright-wall estimates only and prove with a sample. [X]

### 6.5 Load limits and humidity
- Typical load limits for corrugated displays or shelves: not found. A museum shelving thread and metal shelving listings do not apply. [not found]
- Fibre Box Association BCT loss at 80% RH: 32% (Table quoted by Georgia Tech); a linear model predicts 27% at 80% RH; rule of thumb 10 points of RH change gives about 10% change in SCT, ECT and BCT. [C9, C]
- Board moisture content normally 6.5% to 9.5%; below that it cracks, above it loses compression strength. [C10, C]
- A 2019 FBA-led test of about 3,000 boxes at 30 to 90% RH was meant to update the mid-1990s environmental factors; values not published in the article. [C24, C]
- A trade article (search excerpt) says stacking strength falls by more than 60% above 95% RH. Secondary, unverified. [C42, S]
- Cyclic humidity is worse than constant humidity for stacked boxes (Korean study excerpt, and Georgia Tech creep slides). [C42 S; C8 C]
- Derating factors by RH for stands (50, 70, 80, 90%): only the 80% figure (32%) was found. [C9, C]

---

## 7. Nesting on a press sheet

- Bobst ExpertCut 1.7 | 2.1: min sheet 730 x 520 mm; max sheet 1700 or 2100 x 1300 mm; max cutting size 1700 or 2100 x 1275 mm; board 0.75 to 9 mm. [C17, C]
- Other Bobst machines (search excerpts): VisionCut 16 16 PR cutting size 1600 x 1075 mm, gripper margin 15 (+3 / -4) mm; ExpertCut 16 16 PR sheet 1600 x 1100 mm; MasterCut 106 PER cutting size 1060 x 746 mm, gripper margin 9 to 17 mm. [C18, S]
- A 750 x 1050 mm class litho die cutter: sheet max 750 x 1050, min 350 x 400, gripper margin 8 to 12 mm adjustable, rule height 23.8 mm. [C18, S]
- Gripper margins cluster at 8 to 17 mm; rule height 23.8 mm. [C18 S; C5 G]
- Litho sheet 720 x 1020 mm (B1 class) appears as the Invercote board sheet size in a retailer listing. [C39, S]
- Standard corrugated sheet sizes, gutters between parts, common-edge nesting dimensions, die-cut yield ranges, interlocked nesting and inserts in the parent's waste: not found as numbers. [not found]
- Kongsberg-class tables and Bobst limits suggest: stay inside the gripper-free area (sheet minus gripper minus side margins), keep to the machine's max cutting size and board thickness. [C17 C; X]
- Sources note stacking lips and anti-nesting features are used so blanks feed into erectors, with no dimensions. [C22, C]
- X engine defaults, flagged as my numbers only: gutter between parts 4 mm (2 x rule thickness + stripping stability), sheet margin 15 mm gripper side and 10 mm other sides, common-line cuts allowed only on straight cuts away from perforations. [X]

---

## 8. Ship flat and assemble in store

- Walmart's "Five Easies" (via SPS Commerce, supplier community, not Walmart's own file): identify, open (no knife or cutter; skip tape over perforations), stock (stable, one step), shop, dispose. Print product info on at least two sides; one or two people should be able to flatten or fold the pack for recycling. No assembly time stated. [C19, C]
- ECR/GS1 Germany guideline (via THIMM page, search excerpt): opening should need minimum time and staff, opening mechanism clearly marked, injury risk removed. No seconds or headcount. [C43, S]
- Sources on displays advise clear fold lines, minimal steps, numbered or pictorial instructions printed on the shipper, tuck-locks to replace glue, pre-scored perforations for controlled opening, and testing prototypes for compression, drop and stability. [C23 C; C44 S]
- Reusable displays should fold easily; PDQ displays are pallet-sized loads placed straight on the floor. [C19, C]
- Assembly time targets, step counts, one-person rules, no-tool definitions, glue vs hot-melt policy, Shop!/POPAI guidelines, retailer tip-over angle and load tests: NOT FOUND. The retailer vendor guides (Dollar Tree PDF returned 403; Walmart, Target not publicly indexed) were not readable. [not found]
- ISTA-style vibration, drop and compression tests are recommended for shippers but no tip threshold was found. [C44, S]
- X engine defaults: at most 6 assembly steps, one person, no tools, tuck locks and slots only, no glue, fold-flat in under 60 s target. These are unsourced design targets, not retailer rules. [X]

---

## 9. Cut-and-fold prototypes

- Structural designers proof a die by cutting a "white sample" from the die line on a flatbed sample table (Kongsberg or Zund class) and then folding and assembling it by hand; job postings list this as core work. [C45, S]
- Postings also describe validating structural integrity and print registration with built samples before production release, and using ArtiosCAD with sample tables for client mock-ups. [C45, S]
- ArtiosCAD Preflight flags quality issues in the design and validates best-practice principles including Bobst ABC guidelines. [C26, S]
- ArtiosCAD offers a tab-and-slot assembly tool with a 3D view that assembles display components "with a few clicks", a snap tab/slot recogniser, and a parametric template store. [C26, S]
- No source gave a formal proof procedure or fit tolerance. X checklist for the engine's proof sheet, all my own: (1) every crease folds to its expected angle without liner pop on both sides; (2) each tab enters its slot with finger pressure, holds after release, and does not bulge the neighbouring panel; (3) the product sits in its hole at the planned depth; (4) the unit stands, takes a 3 degree lean and the product weight on a flat floor; (5) fold-flat state fits the planned shipper; (6) measure inside dimension against crease-to-crease minus one thickness (FEFCO) and compare with the sample; (7) check the grain/flute direction labelled on the sheet matches the die; (8) record crease cracks, wandering folds and cut-through ties. [X]

---

## Numbers usable as engine rules

| Rule name | Value | Unit | Sources |
|---|---|---|---|
| Inside length/breadth from crease-centre distance | minus 1 x board thickness | mm | C1 (P) |
| Inside height from crease-centre distance | minus 2 x board thickness | mm | C1 (P) |
| Outside gain per crease (symmetric default) | about 0.5 x thickness | mm | C1 P, X |
| Neutral axis position (alternative) | about 0.5 x caliper from inner face, may differ | mm | C2 (C) |
| Compressed thickness used for crease maths | board thickness after compression (0.5 to 1.3 for Cito calculator) | mm | C3, C5 |
| Crease channel depth | about e (compressed thickness) | mm | C5 (G), C3 |
| Crease channel width | 2 x e + rule width | mm | C5 (G), C3 |
| Reverse crease channel (corrugated) | about 2 x e + nib width | mm | C7 (C) |
| Reverse crease channel (solid board) | about 1.5 x t + nib width | mm | C7 (C) |
| Cutting rule height | 23.8 | mm | C4, C5, C18 |
| Creasing rule height | 23.8 minus e | mm | C5 (G) |
| Creasing rule thickness (corrugated) | at least 3 pt = 1.05 | mm | C4 |
| Metal-base strip rule shortening | 0.2 | mm | C3 |
| Die board thickness (corrugated / folding board) | 15 / 18 | mm | C4 |
| Double crease (180 degree) centre spacing range | 3 to 8 | mm | C6 |
| Double crease channel depth / width | 0.6 to 1.0 / 5.0 to 10.0 | mm | C6 |
| Double crease shoulder | 6 | mm | C6 |
| Perforation cut and tie (1-18 TPI) | 0.5 to 2 each | mm | C13 (label industry) |
| Perforation tooth size | 0.8 to 12 | mm | C13 |
| Perforation tie default | 0.8 | mm | C13 |
| Micro-perforation density | 28 to 45 | TPI | C13 |
| Zipper rule tooth spacing | 6 to 12 | mm | C29 (S) |
| Partial score depth | 30 to 70 (25 to 85 range) | % of thickness | C31 (S) |
| CFF2 line numbers | cut 1, crease 2, perf 3, score 4, zipper 41, cut/crease 42 | code | C12 (S) |
| DDES2 line numbers | knife 100, crease 200, perf 300, cut/score 400, cut/crease 500 | code | C12 (S) |
| Die-cut tolerance | +/-1 to 3 | mm | C22 (C) |
| Flute nominal height E / B / C | 1.6 / 3.2 / 4.0 | mm | C10 (C) |
| Flute nominal height A / F | 4.8 / 0.8 | mm | C10 (C) |
| McKee simplified constant | 5.87 | dimensionless (lbf, lbf/in, in) or (N, N/mm, mm) | C9, C8, X |
| McKee full | 2.028 x ECT^0.746 x (sqrt(D_MD D_CD))^0.254 x Z^0.492 | lbf (inch units) | C8 |
| C-flute take-up factor | about 1.42 to 1.43 | ratio | C8, C9 |
| BCT loss at 80% RH | 32 | % | C9 |
| BCT change per 10 RH points | about 10 | % | C9 |
| Board moisture content (normal) | 6.5 to 9.5 | % | C10 |
| Press max sheet (large) | 1700 or 2100 x 1300 | mm | C17 |
| Press min sheet (large) | 730 x 520 | mm | C17 |
| Board thickness range on large press | 0.75 to 9 | mm | C17 |
| Gripper margin | 8 to 17 (15 common) | mm | C18 (S) |
| Litho sheet size B1 class | 720 x 1020 | mm | C39 (S) |
| Walmart SRP: info printed on | at least 2 sides | sides | C19 |
| Slot width (maker practice, cardboard) | thickness minus kerf minus 0.1 to 0.2 | mm | C36 (S) |
| Stand assembly (unsourced default) | at most 6 steps, no tools, one person | steps | X |

---

## Not found

- Per-flute allowance values (E, F, B, C, BE) at folds, and a value for panels nested inside panels.
- Cap width as a multiple of caliper for 180 degree folds; double-crease spacing as a multiple of caliper; half-cut depth for hinges.
- Cut-tie ratios 3x3 and 6x6 mm and zipper-rip dimensions for corrugated tear strips; nick size for corrugated rules.
- ArtiosCAD default colours, layer names and half-cut linetype; any DDES file specification.
- Grain/flute: quantified crack rate across vs along flutes; column-strength loss with flute angle.
- Minimum tab width and length, slot width as caliper plus play for corrugated, slot length vs tab, end radii, barbed-head overhang, minimum cut-to-crease and cut-to-edge, minimum panel between creases, minimum web between holes, tab corner radii.
- Hole clearance per product, platform depth as share of product height, lean, product-fit tolerance.
- Single-wall ECT grade tables by flute, litho-lam calipers, SBS and FBB tables from Metsä, Stora Enso, Iggesund (only search-excerpt values).
- Typical load limits for corrugated displays; FBA humidity table beyond the 80% RH entry; BCT stacking safety factors.
- Standard corrugated sheet sizes, gutter widths, common-edge nesting dimensions, die-cut yield percentages.
- Assembly time targets, step counts, retailer tip-over and load tests, Shop!/POPAI documents, Target/Walmart display guides.
- A published cut-and-fold proofing procedure with tolerances.
- Sources that failed to open: Kodak help pages (certificate error), Dollar Tree vendor guide (403), 3M dieline PDF (403), Iggesund Incada Exel PDF (500), voestalpine (redirect error), RISE fold-cracking page (redirect), Papers Specs paperboard slides (no relevant text), Georgia Tech Guntersville slides (no usable numbers).
- The ECMA Code, Fibre Box Handbook, Iggesund Graphics Handbook, Metsä and Stora Enso handbooks were not retrieved here; the engine already holds carton rules from ECMA and Iggesund.

---

## Sources

| id | grade | title and publisher | URL | accessed | what it gave |
|---|---|---|---|---|---|
| C1 | P | FEFCO Recommendation No. 101, internal dimensions of flap-type cases (July 2006), FEFCO | https://www.fefco.org/sites/default/files/documents/RECOMMENDATIONS__101.pdf | 2026-10-31 | Crease-centre minus 1 (L,B) or 2 (H) thicknesses; creasing allowance definition |
| C2 | C | Packmage CAD note 469-B (in-loss / out-gain), Packmage | https://www.packmage.com/Cad/Document/469-B | 2026-10-31 | Neutral axis, half-caliper, worked 2 cm example |
| C3 | C | Cito die-cutting lesson IV: corrugated tips, PrintWeek India | https://www.printweek.in/features/citos-die-cutting-creasing-lesson-iv-tips-corrugated-board-23267?amp=1 | 2026-10-31 | Channel formula, base strip 0.2 mm, cracking causes |
| C4 | C | Cito die-cutting lesson III: cutting die and creasing matrix, PrintWeek India | https://www.printweek.in/features/citosdiecuttingcreasinglessoniiibasicsselectingcuttingdiecreasingmatrix-23185?amp=1 | 2026-10-31 | Rule heights, 2 pt / 3 pt, die board 15 / 18 mm |
| C5 | G | Cito Abakus online, corrugated creasing calculator, Cito | https://cito.de/en/AE/boxline/rillzurichtungen/cito-abakus_online/wellpappe | 2026-10-31 | A about e, B = 2e + d, h = 23.80 - e, 0.5-1.3 mm |
| C6 | C | CITO BASICplus RYU double crease, Cito | https://www.cito.de/en/CH/boxline/creasing_matrix/cito-basicplus/cito-basicplus-ryu/ | 2026-10-31 | 180 degree double crease spacing, depth, width |
| C7 | C | CITO PLAST reverse crease, Cito | https://www.cito.de/en/BG/boxline/creasing_matrix/cito_plast/cito_plast_reverse_crease/ | 2026-10-31 | Reverse crease uses, thickness range, channel rules |
| C8 | C | Predicting Box Compression Strength, R. Popil, Georgia Tech IPST | https://research.gatech.edu/sites/default/files/rbi/pdfs/Predicting%20Box%20Compression%20Strength_3.pdf | 2026-10-31 | Simplified and full McKee, Whitsitt, stiffness; text extracted locally |
| C9 | C | Effects of Moisture Content on BCT: FBA Loss Factors, R. Popil, Georgia Tech | https://research.gatech.edu/sites/default/files/2021-06/effects-of-moisture-content-on-box-compression-strength.pdf | 2026-10-31 | McKee with units, 32% loss at 80% RH, linear RH model |
| C10 | C | Corrugated fiberboard, Wikipedia | https://en.wikipedia.org/wiki/Corrugated_fiberboard | 2026-10-31 | Flute table, moisture 6.5-9.5% |
| C11 | C | Dieline design, Packaging School | https://packagingschool.com/lessons/dieline-design | 2026-10-31 | Scoring allowance concept, layers; no numbers |
| C12 | S | Kodak Workflow help: CFF2 / DDES2 line types, Kodak | https://workflowhelp.kodak.com/x/cYZaEg | 2026-10-31 | Line codes and colours (search excerpt; fetch failed on certificate) |
| C13 | C | Perforations technical overview (2016), Avery Dennison | https://label.averydennison.com/content/dam/averydennison/lpm-responsive/na/doc/technical-bulletins/technical marketing bulletins/perforations-technical-bulletin.pdf | 2026-10-31 | TPI classes, cut/tie 0.5-2 mm, 0.032 in tie; text extracted locally |
| C14 | P | US5537905A Nicked cutting rule, Google Patents | https://patents.google.com/patent/US5537905 | 2026-10-31 | Nick 0.007 in, depth 0.025 in, tie size (paper web) |
| C15 | P | US5690601A Slitting and scoring corrugated sheets for folding, Google Patents | https://patents.google.com/patent/US5690601 | 2026-10-31 | CD vs MD scores, liner tuck/pop on 180 degree fold |
| C16 | C | What is the grain on paperboard, Lamitech | https://www.lamitech.com/lamitech-news/what-is-the-grain-on-paperboard/ | 2026-10-31 | Fold with grain; underlined dimension |
| C17 | C | EXPERTCUT 1.7 / 2.1 specifications, Bobst | https://www.bobst.com/auen/products/flatbed-die-cutting/die-cutters/specifications/machine/expertcut-17-21 | 2026-10-31 | Sheet and cutting size, 0.75-9 mm |
| C18 | S | Bobst and used-machine listings (search results) | https://www.bobst.com/usen/products/flatbed-die-cutting/die-cutters/specifications/machine/visioncut-16-16-pr | 2026-10-31 | Gripper margins, other press sizes |
| C19 | C | The Five Easies of Shelf Ready Packaging, SPS Commerce | https://www.spscommerce.com/community/articles/what-are-the-5-easies-of-retail-ready-packaging | 2026-10-31 | Five easies, two-sides print |
| C20 | C | How to specify corrugated board, DS Smith Sheetfeeding | https://dssmith.com/sheetfeeding/insights/about-corrugated/how-to-specify-corrugated-board | 2026-10-31 | Flutes parallel to first sheet dimension |
| C21 | C | Corrugated cardboard guide (Nassco) and Do you speak corrugated (PCA glossary), text extracted locally | https://www.nasscoinc.com/literature/Nassco_WebChart_CorrugatedCardboardGuide_r2.pdf | 2026-10-31 | Flute characteristics; BMC ECT 32 lb/in example |
| C22 | C | Die cut corrugated box technical guide, Racklify (blog; weak) | https://racklify.com/encyclopedia/die-cut-corrugated-box-technical-guide-to-design-and-manufacturing/ | 2026-10-31 | +/-1-3 mm tolerance, microflute caution |
| C23 | C | Designing effective display trays, Racklify (blog; weak) | https://racklify.com/encyclopedia/designing-effective-display-trays-materials-construction-and-best-practices/ | 2026-10-31 | Qualitative tray and assembly advice; no numbers |
| C24 | C | Engineering boxes for relative humidity, Packaging Strategies (FBA column) | https://packagingstrategies.com/articles/91064-engineering-boxes-for-relative-humidity-in-the-distribution-environment | 2026-10-31 | 3,000-box RH test, no values |
| C25 | S | Search excerpts: fold-score patents (US6162155 and family), vertical-flute display patents, TAPPI T 839, FE study of 180 degree folding | https://patents.google.com/patent/US6162155 | 2026-10-31 | Wander, vertical flutes, ECT orientation |
| C26 | S | ArtiosCAD pages and trade coverage (Esko; imagereportsmag; Mimaki-hosted datasheet) | https://imagereportsmag.co.uk/?p=1801 | 2026-10-31 | Tab-slot tool, preflight, thickness-driven dimensions |
| C27 | S | Scoring chipboard forum thread, Briar Press | https://briarpress.org/17963 | 2026-10-31 | Channel = rule + 2 x stock |
| C28 | S | Die specification form (printer), Jotform | https://form.jotform.com/261062552540045 | 2026-10-31 | TPI/cut/nick sample pairs |
| C29 | S | Scandie special rules, voestalpine | https://voestalpine.com/precision-strip/products-brands/scandie/special-rules | 2026-10-31 | Zipper rule tooth spacing 6-12 mm (fetch failed) |
| C30 | S | HalfCut guide (signs) and SmartPress glossary | https://uksignboards.com/wp-content/uploads/attachments/HalfCut_inSignLab.pdf | 2026-10-31 | Half-cut / kiss-cut definitions |
| C31 | S | Carton with improved folding, patent 20180022499, Justia | https://patents.justia.com/patent/20180022499 | 2026-10-31 | Score depth 25-85% |
| C32 | S | Fold cracking troubleshooting, RISE MoRe | https://more.se/en/services/trouble-shooting/fold-cracking | 2026-10-31 | Delamination in scoring (fetch redirected) |
| C33 | S | Global packaging dieline requirements, 3M | https://multimedia.3m.com/mws/media/2619412O/global-packaging-dieline-requirements.pdf | 2026-10-31 | Spot colour per line type, 1 pt, legend (403 on fetch) |
| C34 | S | Cuts and creases file supply, printing.com | https://www.printing.com/uk/file-supply/5180 | 2026-10-31 | Dashed/spot colour conventions |
| C35 | S | Dollar Tree FD Vendor Guide Part 5; Easysigns flute guide; Kinter corrugated display hooks | https://corporate.dollartree.com/_assets/_39d1c3acf241280d452921a9e95f7d6b/dollartreeinfo/db/1137/9047/file/FD_Vendor_Guide_Part_5_Product_and_Packaging_Carton_and_Display_Packaging_Requirements.pdf | 2026-10-31 | Vertical flute direction; B/C slot sizes (403 on fetch) |
| C36 | S | Fab Academy / MIT CBA laser-cut cardboard kerf notes | https://fab.cba.mit.edu/classes/863.25/people/RaySong/pages/week2.html | 2026-10-31 | Slot = thickness minus kerf minus clearance |
| C37 | S | Die-cutting / slotting machine pages and 4over4 hole-size help | https://www.4over4.com/.well-known/okf/help/what-is-the-minimum-hole-size-you-can-die-cut.md | 2026-10-31 | 7 mm slot, 8 mm score spacing, 1/16 in hole |
| C38 | S | Retail lipstick display listings (Displays2Go, others) | https://www.displays2go.com/P-36852/Tiered-Acrylic-Lipstick-Display-Rack-Multi-Sized-Holes?fulldetails=1 | 2026-10-31 | Hole sizes 0.7-1 in |
| C39 | S | Invercote / Incada Exel / EnsoCoat listings and datasheets | https://pre.iggesund.com/globalassets/iggesund/products/incada-family/product-specifications/incada-exel-en-pdf | 2026-10-31 | Calipers, grammage, tolerances (fetch 500; excerpts only) |
| C40 | S | Corrugated flute guides (Tinybox, Packwire, Paperlust, Racklify) | https://www.tinyboxcompany.co.uk/blog/post/choose-the-right-flute-for-strength-and-weight | 2026-10-31 | Finished-board caliper ranges |
| C41 | S | Thai study of the simplified McKee formula (Agriculture and Natural Resources) | https://li01.tci-thaijo.org/index.php/anres/article/download/267446/180071 | 2026-10-31 | 5.8745 constant, metric units |
| C42 | S | Humidity studies and trade articles (Clemson thesis, KoreaScience, NMFTA) | https://nmfta.org/news/packaging-in-the-summertime-how-summer-humidity-destroys-paper-and-corrugated-packaging-and-what-to-do-about-it/ | 2026-10-31 | >60% loss near 95% RH, cyclic RH |
| C43 | S | Merchandise presentation through packaging, THIMM (ECR / GS1 Germany guideline summary) | https://www.thimm.com/en/sales-promotion/merchandise-presentation-through-packaging-shelf/ | 2026-10-31 | Opening time and staff principle |
| C44 | S | Racklify shipper-display pages; nwpaperbox display article | https://www.nwpaperbox.com/blog/corrugated-pop-displays-that-move-product | 2026-10-31 | Display assembly and testing advice |
| C45 | S | Structural designer job postings (jobright, Paylocity, Zenpack) | https://recruiting.paylocity.com/Recruiting/Jobs/Details/4392871 | 2026-10-31 | White samples on sample tables, validation |

Local text extraction (pdftotext, PyMuPDF) of PDFs already downloaded by WebFetch was used for C1, C8, C9, C13, C21 and was not counted as extra fetches.

Calls: 29 searches, 34 fetches.
