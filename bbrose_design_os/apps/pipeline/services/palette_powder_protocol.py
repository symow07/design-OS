"""M6 §14 — the POWDER_CHARACTERIZATION_PROTOCOL, declared before use.

One protocol, five sub-rigs, nine powder families. The M5 law carries
over unchanged: a sub-rig is selected by the PHYSICAL CHARACTERIZATION
QUESTION a family raises, never by the desired answer; validity windows
and pass laws are declared HERE, before any measurement exists; a family
pair is distinct only when the predeclared axes clear on a commissioned
rig with behaving negative controls; and there is no per-shade rig —
shades share their family's rig, because a shade is a colour and a
family is a structure.

§16's structural demand is the spine of the taxonomy: the families
differ in STRUCTURE (discrete particles, flake fields, domed vitrified
surfaces, spatial colour), not in slider positions. GLITTER versus
SHIMMER is the canonical case — a discrete bright-outlier population
versus a continuous micro-flake sheen — and a protocol that cannot make
that distinction on its declared axes has failed regardless of how the
renders look.

REALIZATION STATUS: this module is the §14 DECLARATION. The shader
realizations, the swatch fixtures, the rig commissioning runs and every
measurement are NOT implemented here and nothing below pretends they
are; ``protocol_status()`` says so in machine-readable form.
"""
from __future__ import annotations

import hashlib
import json

SCHEMA = "powder_characterization_protocol/1.0"
VERSION = 1

# --------------------------------------------------------------------------
# §16 — the nine powder families, structurally declared
# --------------------------------------------------------------------------

POWDER_MATTE = "POWDER_MATTE"
POWDER_SATIN = "POWDER_SATIN"
SHIMMER = "SHIMMER"
POWDER_METALLIC = "POWDER_METALLIC"
GLITTER = "GLITTER"
BAKED = "BAKED"
MARBLED = "MARBLED"
PRESSED_POWDER = "PRESSED_POWDER"
CREAM = "CREAM"

POWDER_FAMILIES = (POWDER_MATTE, POWDER_SATIN, SHIMMER, POWDER_METALLIC,
                   GLITTER, BAKED, MARBLED, PRESSED_POWDER, CREAM)

#: What makes each family a STRUCTURE rather than a slider position,
#: and which sub-rig answers its physical question.
FAMILY_STRUCTURE = {
    POWDER_MATTE: {
        "structure": "loose-milled micro-rough diffuse surface",
        "distinct_from_case_matte": "powder micro-texture scatters with "
                                    "visible grain; moulded ABS does not",
        "sub_rig": "DIFFUSE_MICROTEXTURE_RIG",
    },
    POWDER_SATIN: {
        "structure": "finely-milled surface with a soft directional "
                     "sheen from aligned platelet fillers",
        "sub_rig": "DIFFUSE_MICROTEXTURE_RIG",
    },
    SHIMMER: {
        "structure": "CONTINUOUS field of fine metallic flakes below "
                     "individual visibility — sheen, no discrete events",
        "sub_rig": "FLAKE_REFLECTION_RIG",
    },
    POWDER_METALLIC: {
        "structure": "dense flake loading reading as a metal surface "
                     "while remaining a powder (no mirror coherence)",
        "sub_rig": "FLAKE_REFLECTION_RIG",
    },
    GLITTER: {
        "structure": "DISCRETE sparse large particles — an outlier "
                     "population of individually visible sparkle events",
        "canonical_contrast": "SHIMMER — continuous versus discrete is "
                              "a statistical structure, not a brightness",
        "sub_rig": "GLITTER_PARTICLE_RIG",
    },
    BAKED: {
        "structure": "wet-baked dome: curved surface geometry with a "
                     "partially vitrified, slightly glossed crust",
        "sub_rig": "BAKED_GEOMETRY_RIG",
    },
    MARBLED: {
        "structure": "spatial multi-tone colour structure — regions, "
                     "not a uniform field",
        "sub_rig": "MARBLING_STRUCTURE_RIG",
    },
    PRESSED_POWDER: {
        "structure": "compacted flat pan surface with a faint "
                     "compaction sheen and press-ring",
        "sub_rig": "DIFFUSE_MICROTEXTURE_RIG",
    },
    CREAM: {
        "structure": "non-powder emulsion: smooth, micro-texture-free, "
                     "soft specular",
        "canonical_contrast": "POWDER_SATIN — smoothness versus milled "
                              "grain at matched gloss",
        "sub_rig": "DIFFUSE_MICROTEXTURE_RIG",
    },
}

# --------------------------------------------------------------------------
# §14 — the five sub-rigs, each owning one physical question
# --------------------------------------------------------------------------

SUB_RIGS = {
    "DIFFUSE_MICROTEXTURE_RIG": {
        "physical_question": "how does a surface's micro-texture shape "
                             "its diffuse and near-specular response?",
        "apparatus": "the validated M5 dielectric lobe rig (broad "
                     "diffuse + compact specular + fill), unchanged — "
                     "the question is the same, so the rig is reused, "
                     "not rebuilt",
        "validity": {"peak_scene_linear_window": [0.35, 0.92],
                     "max_clipped_samples": 0},
        "families": [POWDER_MATTE, POWDER_SATIN, PRESSED_POWDER, CREAM],
    },
    "FLAKE_REFLECTION_RIG": {
        "physical_question": "what does a flake field reflect of a "
                             "structured environment, and how coherently?",
        "apparatus": "the validated M5 reflective rig (neutral emissive "
                     "panels, mirror commissioning reference), unchanged",
        "validity": {"mirror_reference_min_pattern_contrast": 0.20,
                     "min_subject_peak_scene_linear": 0.05},
        "families": [SHIMMER, POWDER_METALLIC],
    },
    "GLITTER_PARTICLE_RIG": {
        "physical_question": "is the bright response a continuous field "
                             "or a population of discrete events?",
        "apparatus": "compact specular source over a flat swatch, "
                     "resolution high enough that one particle spans "
                     "multiple pixels; commissioned with a zero-particle "
                     "control that must produce a zero event count",
        "validity": {"min_resolvable_particle_px": 3,
                     "zero_particle_control_max_events": 0},
        "families": [GLITTER, SHIMMER],
        "note": "SHIMMER appears here as the negative contrast: its "
                "event count must stay at the control level while "
                "GLITTER's must not",
    },
    "BAKED_GEOMETRY_RIG": {
        "physical_question": "does the surface carry macroscopic dome "
                             "geometry and a crust gloss gradient?",
        "apparatus": "raking light at grazing incidence across the pan "
                     "profile — geometry reads as a shading gradient a "
                     "flat pressed pan cannot produce",
        "validity": {"raking_elevation_deg_max": 12,
                     "flat_reference_max_gradient": "declared at "
                     "commissioning from the flat pressed control"},
        "families": [BAKED, PRESSED_POWDER],
    },
    "MARBLING_STRUCTURE_RIG": {
        "physical_question": "is colour spatially structured into "
                             "regions, or a uniform field?",
        "apparatus": "flat even illumination (no specular emphasis) — "
                     "the question is chromatic-spatial, so the light "
                     "must not add luminance structure of its own",
        "validity": {"illumination_uniformity_max_deviation": 0.08},
        "families": [MARBLED],
    },
}

#: Pass law, fixed here as in M5: at least 2 INDEPENDENT axes at >= 25%
#: relative effect (absolute bars for bounded/correlation axes), with
#: negative controls behaving. Declared per sub-rig BEFORE any
#: measurement; dependent axes are SUPPORTING and never counted.
#:
#: OWNER-AMENDED 2026-08-08 (authorization: the owner's transmission of
#: M6_INDEPENDENCE_AMENDMENT_PROMPT.md IS the authorization; this is an
#: owner-declared amendment executed, not a unilateral one). The
#: amendment is STRICTLY ADDITIVE: it adds the conjunctive independence
#: definition below and moves NO bar — required_independent_axes,
#: relative_effect_bar, supporting_axes_never_count are byte-unchanged
#: (diff-proven in the amendment record). The prior single-condition R5
#: definition (census Spearman only) is SUPERSEDED IN PLACE by the
#: conjunctive form; its text survives in the repair declaration.
PASS_LAW = {
    "required_independent_axes": 2,
    "relative_effect_bar": 0.25,
    "supporting_axes_never_count": True,
    "declared_before_measurement": True,
    "independence": "CONJUNCTIVE_PAIR_SPECIFIC_SEE_INDEPENDENCE_LAW",
}

#: The amended independence law — owner-declared, conjunctive,
#: pair-specific, strictly additive to the census condition.
INDEPENDENCE_LAW = {
    "sweep_validity_1a": (
        "a sweep over a single driver is VALID as an independence "
        "instrument only if its pairwise |rho| matrix contains at least "
        "one pair reading at or below the R5 ceiling of 0.80. A sweep in "
        "which every measured pair tracks above the ceiling is recorded "
        "as SWEEP_DEGENERATE_UNDER_DRIVER and yields no independence "
        "evidence in either direction — it may not disturb a verdict and "
        "may not support one. Rationale, declared before any matrix was "
        "read: rank correlation along a monotone driver is 1.0 by "
        "construction for any two monotonically-responding axes; "
        "divergence somewhere in the matrix is the only demonstration "
        "that the instrument resolves difference rather than restating "
        "the driver's own ordering — the sweep-space analogue of the "
        "documented N=4 census degeneracy. This condition is SYMMETRIC: "
        "it can void the number that threatens three verdicts and it can "
        "equally void a number that would have rescued one."),
    "conjunctive_law_1b": (
        "two axes may both count toward one pair's two-axis requirement "
        "only if BOTH hold: (i) CENSUS CONDITION — unchanged, unmoved, "
        "not reinterpreted: |rho| across the family census at or below "
        "0.80, subject to the recorded census-size caveat; (ii) DRIVER "
        "CONDITION — for every parameter that (a) is declared in the "
        "contract or is a builder constant proven to reach the render, "
        "(b) is proven REALIZED rather than NEVER_ARRIVES, and (c) "
        "actually differs in value between the two families of this "
        "specific pair, a sweep of that parameter on the rig carrying "
        "the counted axes must not show the two counted axes tracking "
        "above 0.80 — provided that sweep is VALID under 1a. A parameter "
        "that does not differ between the pair's families is not a "
        "driver for that pair. A differing but non-sweepable parameter "
        "is NON_SWEEPABLE_DRIVER: the pair is PASS_WITH_UNTESTED_DRIVER "
        "on the standing obligations list — not a FAIL (no tracking "
        "evidence exists), not clean (the check could not run)."),
    "asymmetry_1c": (
        "any verdict that IMPROVES under this amendment (a FAIL becoming "
        "PASS, a fenced provisional becoming clean) is NOT committed — "
        "recorded as AMENDMENT_INDUCED_IMPROVEMENT and held for the "
        "owner. Verdicts that DEGRADE are committed immediately. An "
        "amendment that can only help is a rescue vehicle; this "
        "asymmetry is what prevents it from becoming one."),
    "strictly_additive": (
        "the amendment removes no condition and moves no bar; no pair "
        "that fails today can pass because of it"),
    "owner_authorization": "M6_INDEPENDENCE_AMENDMENT_PROMPT.md, 2026-08-08",
    "containment_1e": (
        "a NOT_COMMON_DRIVER conclusion — reached because a counted "
        "axis's response to a driver falls under its qualification "
        "threshold — is valid ONLY if the swept range contains the "
        "interval between the two families' values of that driver for "
        "that pair (render-effective values where a side declares but "
        "never arrives; for a block absent by structure, the interval "
        "runs from the block-absent effective value to the "
        "block-present value, and the sweep must span it; a scale or "
        "shape member of an absent block has no absent-side value — "
        "its containment is governed by the block's amplitude member). "
        "If the range contains the interval, the reading stands and a "
        "wider sweep adds nothing: wider sweeps measure products that "
        "do not exist. If it does not, the reading is "
        "UNTESTED_AT_SEPARATING_STIMULUS, not NOT_COMMON_DRIVER, and "
        "the driver must be re-swept over at least the containing "
        "interval before the pair may be ruled. The criterion is "
        "containment, not width — checkable geometry, not judgment."),
    "conservation_1f": (
        "for each pair and each counted axis, the axis's measured "
        "inter-family effect must be accountable by the union of the "
        "swept drivers' measured spans over their inter-family "
        "intervals. If the measured effect materially exceeds what "
        "every enumerated driver can produce across the interval that "
        "actually separates the families, the driver enumeration is "
        "proven incomplete and the residual must be named — a specific "
        "parameter, a specific builder constant, or UNACCOUNTED_CAUSE. "
        "A pair carrying an UNACCOUNTED_CAUSE residual may not be a "
        "clean PASS: its honest status is PASS_WITH_UNTESTED_DRIVER "
        "with the residual magnitude stated, because an unenumerated "
        "cause is by definition an untested driver. Rationale declared "
        "before the numbers: NOT_COMMON_DRIVER is a null result "
        "discharging a safety condition, and this project has been "
        "wrong three times in exactly that pattern (the sub-pixel "
        "zero, the silent zero on RAKING_SHADOW_FRACTION, the "
        "constant-vector rank correlation). Conservation converts 'we "
        "found nothing' into a bounded claim about how much there was "
        "to find."),
    "degenerate_statistic_guard_1g": (
        "no rank correlation may be computed in this codebase against "
        "a zero-variance vector — the guard RAISES rather than "
        "returning a number. Defect class registered as "
        "DEGENERATE_INPUT_PLAUSIBLE_OUTPUT (third of its kind after "
        "the N=4 census degeneracy and the silent-zero floor), "
        "alongside DECLARED_BUT_UNREALIZED and BUILDER_CONSTANT. The "
        "guarded implementation (palette_statistics.guarded_spearman) "
        "is the only path by which a correlation may be computed."),
    "second_owner_authorization":
        "M6_DRIVER_COMPLETENESS_PROMPT.md, 2026-08-08 — strictly "
        "additive again; no bar moved, proven by diff",
    "adequacy_1i": (
        "ADEQUACY PRECONDITION. Every comparison of a measured "
        "statistic against a threshold in this protocol has a "
        "precondition: the reading must be a measurement of which "
        "side of the threshold it falls on. It is such a measurement "
        "only if the absolute margin between reading and threshold "
        "EXCEEDS the replicate spread of that same statistic under "
        "the same instrument, measured across the instrument's "
        "declared seed ensemble. Margin not exceeding spread yields "
        "ADEQUACY_PRECONDITION_UNMET — not a verdict in either "
        "direction, never readable as one; no conditional keyed on "
        "the comparison applies, because its precondition failed. The "
        "response is to increase resolving power and re-measure — "
        "never to move the threshold, never to pick the side that "
        "suits, never to commit and challenge afterward. Where no "
        "replicate spread has ever been measured for a statistic the "
        "comparison is ADEQUACY_UNASSESSED until one is. A spread of "
        "a DIFFERENT statistic is not a spread; a deterministic "
        "computation with no seed ensemble is spread-inapplicable "
        "and adequate at any positive margin. Rationale, declared "
        "before the retroactive sweep: a committed verdict acquires "
        "inertia and everything downstream reasons from it — the "
        "cost of staying an unreproducible reading is a delay; the "
        "cost of committing one is a load-bearing number nobody can "
        "dislodge. Retroactive application is mandatory and "
        "symmetric: a PASS found unmet is re-marked exactly as a "
        "FAIL would be."),
    "red_flag_precommitment_1i": (
        "declared BEFORE the retroactive sweep: if 1i disturbs only "
        "verdicts whose disturbance is convenient — stays FAILs and "
        "never unsettles a PASS — that pattern is reported as a "
        "suspicious result requiring explanation, not as a clean "
        "outcome."),
    "third_owner_authorization":
        "M6_MEASUREMENT_ADEQUACY_PROMPT.md, 2026-08-08 — strictly "
        "additive; no bar moved, proven by diff",
    "establishment_1j": (
        "BURDEN OF ESTABLISHMENT. The two non-adequate statuses "
        "differ in remedy, not force, and are never conflated: "
        "ADEQUACY_PRECONDITION_UNMET — spread measured, margin does "
        "not exceed it; positive evidence the instrument cannot "
        "decide at current resolution; remedy is resolving power and "
        "may prove unresolvable. NOT_ESTABLISHED_PENDING_SPREAD — "
        "spread never measured; no evidence either way; remedy is "
        "bounded, known work. Neither may be relied upon; neither is "
        "a FAIL. The burden of establishment falls on the "
        "AFFIRMATIVE claim: adequacy failure removes inferential "
        "license, and which verdict that disturbs depends on which "
        "side of the comparison was asserting something. An "
        "unassessed PASS asserted a bar was cleared — it SUSPENDS "
        "(a property declared with nothing capable of noticing "
        "whether it holds is DECLARED_BUT_UNREALIZED one level up, "
        "and gets no exemption for being ours). An unassessed FAIL "
        "asserted nothing — it refused to certify, and absence of "
        "adequate evidence leaves the thing uncertified: it stands, "
        "re-marked not-certified rather than measured-to-fail. An "
        "unassessed ineligibility exclusion keeps the axis out — "
        "using an axis requires positive evidence of eligibility, "
        "which is exactly what is missing. An unassessed degeneracy "
        "verdict stands — degeneracy is a refusal to extract "
        "information. SELF-CHECK, pre-committed: an application of "
        "1j that RESCUES anything is misapplied; any rescue "
        "encountered is reported, never committed."),
    "fourth_owner_authorization":
        "M6_ESTABLISHMENT_CLOSURE_PROMPT.md, 2026-08-08 — strictly "
        "additive; no bar moved, proven by diff",
    "proxy_status_1k": (
        "UNMET_BY_CONSERVATIVE_PROXY. Where an adequacy comparison "
        "fails against a conservative PROXY spread rather than the "
        "named quantity, the status names both: the proxy used and "
        "the direct quantity 1i asks for. For a cross-family "
        "clearing the named quantity is the clearing itself "
        "recomputed at each seed of the declared ensemble, and its "
        "dispersion; max_seed_only_effect is the same functional at "
        "the null point — a legitimate conservative proxy, not the "
        "test. The status softens nothing: the comparison remains "
        "unestablished and unusable and the burden rule still "
        "suspends what rests on it. It corrects what has been "
        "SHOWN: failure against a surrogate, not the named test."),
    "substitution_1l": (
        "SUBSTITUTION, pre-committed before any number. If a direct "
        "ensemble measurement confirms a counted axis UNMET, the "
        "pair may seek a different second axis — commissioned, "
        "floor-eligible, declared long before the failure. To "
        "prevent cherry-picking: for each affected pair, name EVERY "
        "candidate axis before measuring any (every axis "
        "floor-eligible and R5-permitted alongside the surviving "
        "counted axis, all three properties reported per candidate: "
        "floor-eligible, R5-permitted for this pair, clears its bar "
        "on this pair); measure ALL of them; report ALL effects and "
        "adequacies including failures. A pair passes on a "
        "substitute only if it clears its own bar with margin "
        "exceeding its own directly-measured ensemble spread. If no "
        "candidate qualifies the pair FAILS, recorded as FAIL — and "
        "separately the finding that the two-axis law is "
        "unsatisfiable for that pair on the commissioned instrument "
        "suite. The law does not bend to fit the rig; the rig is "
        "what gets extended, in a declared commissioning, if anyone "
        "later chooses to."),
    "partial_replicate_1m": (
        "A partial replicate is evidence about progress, never "
        "about establishment. Only spreads measured across an "
        "instrument's DECLARED seed ensemble (or better) establish. "
        "Adopted as general law from the establishment-closure "
        "node's strict ruling: the programme exists to refuse "
        "under-measured statistics and does not close nodes by "
        "committing one."),
    "fifth_owner_authorization":
        "M6_SEQUENCING_AND_SUBSTITUTION_RULING.md, 2026-08-08 — "
        "strictly additive; no bar moved, proven by diff",
    "instrument_correction_1n": (
        "INSTRUMENT CORRECTION DURING PROOF (the owner's brief names "
        "this rule 1k; that letter is occupied by the proxy status, "
        "so it is hashed as 1n with the collision recorded). A frozen "
        "proof instrument may be corrected by the executor, before "
        "the verdict is read, only if ALL FIVE hold: (1) a null or "
        "tautological control fails — a case whose correct answer is "
        "known independently of the claim under test; reasoning that "
        "the instrument must be wrong because the claim is believed "
        "true does not qualify. (2) The correction is a NARROWING of "
        "scope to the property actually claimed, and the removed "
        "scope is proven by that control to carry no information "
        "about the claim. (3) STRICTNESS IS NOT RELAXED — zero "
        "tolerance stays zero; any move from exact to approximate is "
        "a bar move and stops the node for owner ruling regardless "
        "of justification. (4) The correction is declared and "
        "committed before the verdict is read. (5) The frozen text "
        "is not re-drafted; the correction is recorded alongside it "
        "with the divergence explained, reported at the boundary as "
        "a first-class item. If any of 1 through 3 fails, the node "
        "stops and escalates. Scope may be narrowed; strictness may "
        "not."),
    "sixth_owner_authorization":
        "M6_MARBLING_INSTRUMENT_REPAIR_PROMPT.md, 2026-08-08 — "
        "strictly additive; no bar moved, proven by diff; A13/A14/"
        "A15 confirmed already carried by the fifth amendment",
    "control_coverage_1p": (
        "CONTROL COVERAGE AT CONDITION. A clearing reading is "
        "self-validating for SENSITIVITY at its own condition — an "
        "instrument reporting a large effect there is demonstrably "
        "not blind there. It is NOT self-validating for SPECIFICITY: "
        "the negative control must hold at every condition where the "
        "axis is counted, and for a cross-member comparison that "
        "means every member's condition, because a large reading may "
        "be the instrument responding to seed or placement at that "
        "condition even where it does not at another. A null or "
        "non-clearing reading is not self-validating for ANYTHING: "
        "it may be counted as a measurement of the subject only "
        "where the positive control passes at that same condition; "
        "otherwise it is INSTRUMENT_NOT_VALIDATED_AT_CONDITION and "
        "carries nothing in either direction — not evidence the "
        "subject is null, not evidence the instrument is blind."),
    "fallback_class_1q": (
        "SILENT_PLAUSIBLE_FALLBACK — the defect class, named at its "
        "fourth appearance: an operation that, given malformed, "
        "absent or unexpected input, silently produces a plausible "
        "in-range result instead of raising. Scope: EVERY measurement "
        "and analysis path — tooling that produces a number which "
        "reaches a record is measurement code, whatever directory it "
        "lives in. Declaring any structural guard now includes a "
        "SCOPE CHECK: what is the class, and does the guard cover "
        "all of it, or only where it was found? The third-appearance "
        "guard (1g) was scoped to rank correlations in the codebase "
        "and did not generalize — recorded, not repeated."),
    "seventh_owner_authorization":
        "M6_CONTROL_COVERAGE_PROMPT.md, 2026-08-08 — strictly "
        "additive; no bar moved, proven by diff",
    "allowlist_burden_1r": (
        "AN ALLOWLIST, EXEMPTION OR SUPPRESSION IS AN AFFIRMATIVE "
        "CLAIM OF INERTNESS and carries the burden of establishment "
        "(1j). No entry may be added to any allowlist without a "
        "recorded disposition establishing that it never affected a "
        "committed number, or naming the numbers it did affect. "
        "Every entry is tri-state and amnesty is not a status: "
        "INERT_PROVEN — shown on retained data never to have fired, "
        "evidence cited; stays allowlisted and is still fixed to "
        "raise eventually under a declared repair node. FIRED — "
        "fired at least once in a computation that reached a record; "
        "NOT allowlisted, enters the repair node with an explicit "
        "void list of the numbers it touched. NOT_ASSESSED — "
        "retained data insufficient to tell; blocks nothing by "
        "itself, but every committed number downstream inherits "
        "not-established status, because a value in its computation "
        "chain is unverified."),
    "eighth_owner_authorization":
        "M6_FALLBACK_FIRING_AUDIT_PROMPT.md, 2026-08-08 — strictly "
        "additive; no bar moved, proven by diff",
    "instrument_competence_1s": (
        "INSTRUMENT COMPETENCE BY CLAIM TYPE. A disposition that "
        "discharges an entry from an allowlist, exemption or "
        "suppression separates into two claims, each requiring an "
        "instrument competent for its type: HISTORICAL (did it fire), "
        "which no static reading can settle, and STRUCTURAL (can any "
        "committed number be downstream of it), which static analysis "
        "can. A structural discharge is permitted only if all five "
        "hold: (1) established by a DECLARED static instrument of "
        "record, not by reading surrounding code; (2) a claim about "
        "EVERY path out of the site, not the typical one; (3) it "
        "claims UNREACHABILITY OF ANY COMMITTED NUMBER — not that "
        "firing is unlikely, not that firing would be harmless; (4) "
        "if the instrument cannot decide, the entry stays "
        "NOT_ASSESSED and inherited status propagates to the numbers "
        "ACTUALLY downstream of it, enumerated, never to the table "
        "wholesale; (5) it is recorded as INERT_BY_UNREACHABILITY, "
        "DISTINCT from INERT_PROVEN, so entries resting on structural "
        "evidence are separable from entries resting on runtime "
        "evidence. Condition 5 is load-bearing: the static "
        "reachability instrument has been found to undercount once "
        "already, and if it undercounts again the "
        "structurally-discharged entries are exactly the set that "
        "reopens."),
    "ninth_owner_authorization":
        "M6_ALLOWLIST_COVERAGE_CLOSURE_PROMPT.md, 2026-08-08 — "
        "strictly additive; no bar moved, proven by diff; label 1s "
        "was free (no collision)",
    "static_reachability_1t": (
        "STATIC REACHABILITY IS SOUND FOR REFUTATION AND UNSOUND FOR "
        "CONFIRMATION. A site in a module not import-reachable from "
        "any declared measurement entry point cannot be called by a "
        "measurement computation, and its structural discharge is "
        "established. A site that IS import-reachable has been shown "
        "NOTHING — not that it fired, not that any committed number "
        "is downstream — and it returns NOT_ASSESSED; only a finer "
        "DECLARED instrument may move it, with its unsoundness "
        "sources enumerated first (dynamic import, getattr dispatch, "
        "decorator/registry indirection, callbacks as values, "
        "eval/exec, plugin loading) and every site turning on one of "
        "them left undecided. The measurement set is checked for "
        "dynamic import BEFORE the graph is trusted: one importlib "
        "call defeats the instrument silently, which would make the "
        "reachability instrument a member of the class it audits — "
        "found means stop and escalate, never substitute an "
        "instrument unbidden. This is 1p one level down: the same "
        "asymmetry, applied to static analysis."),
    "evidence_citation_1u": (
        "A DISPOSITION CITING EVIDENCE MUST NAME THE RECORD, NOT THE "
        "CORPUS. 'The audit proves it' is not a disposition; "
        "'audited computation N evaluated this site at denominator "
        "D' is. Where a set of dispositions is discharged by a set "
        "of records, the JOIN between them is itself a required "
        "deliverable, never an inference. Origin recorded on the "
        "owner's side of the ledger: the firing-audit brief asked "
        "for per-consumer reporting and per-site disposition as "
        "independently satisfiable deliverables, and nothing "
        "required the join — which is how 383 computations were "
        "audited thoroughly while 56 of 62 sites were untouched by "
        "the audit later cited as their evidence."),
    "tenth_owner_authorization":
        "M6_REACHABILITY_INSTRUMENT_PROMPT.md, 2026-08-08 — strictly "
        "additive; no bar moved, proven by diff; labels 1t/1u free "
        "(1o was skipped at the seventh amendment without collision "
        "— recorded, not backfilled)",
    "contemporaneity_1v": (
        "CONTEMPORANEITY OF CITED RECORDS. A record cited under 1u "
        "must be contemporaneous with the computation it "
        "dispositions. Where it is not, the temporal gap is itself a "
        "claim requiring disposition — evidence gathered at one code "
        "state carries to another only where the relevant state is "
        "shown unchanged between them."),
    "constant_resolvable_import_1w": (
        "CONSTANT-RESOLVABLE DYNAMIC IMPORT. A dynamic import whose "
        "target is a compile-time constant is a static import for "
        "1t's purposes, provided the instrument resolves such "
        "imports generally, follows the resolved edge rather than "
        "waiving it, and raises on any non-constant argument."),
    "textual_floor_1x": (
        "TEXTUAL COUNTS ARE LOWER BOUNDS. A count produced by a "
        "textual scan is a floor, not a figure. It may be recorded, "
        "but it may not be cited as the size of a class, and any "
        "disposition resting on the completeness of a textual "
        "enumeration is unestablished."),
    "eleventh_owner_authorization":
        "M6_SCOPE_AND_PROVENANCE_PROMPT.md, 2026-08-08 — strictly "
        "additive; no bar moved, proven by diff; labels 1v/1w/1x "
        "free",
    "declaration_syntax_1y": (
        "DECLARATION IS INDEPENDENT OF SYNTAX. Any value that "
        "reaches a render or a measurement and is not stated in a "
        "contract is an undeclared constant, regardless of the "
        "mechanism by which it enters — literal, default argument, "
        "lookup default, class attribute, environment read or "
        "fallback. Where a contract does state the key, a differing "
        "in-code value is a CONFLICT and a defect. "
        "Declaration-by-construction is a fact about the value, not "
        "about the contract (A23, A46/A47). The record partition: "
        "DECLARED_AGREEING / DECLARED_CONFLICTING / "
        "UNDECLARED_DEFAULT, the last being BUILDER_CONSTANT in "
        "different syntax."),
    "guard_corpus_1z": (
        "EVERY DECLARED STRUCTURAL GUARD CARRIES A SEEDED CORPUS — "
        "a versioned set of synthetic instances spanning every known "
        "shape of the class it protects. The suite fails if the "
        "guard's detector misses any corpus member. A "
        "newly-discovered shape enters the corpus in the same commit "
        "as its discovery. Origin: guard scope failed three times "
        "(A22 rank-correlation scoping, A34 hand-written "
        "reachability list, A41 textual detector missing 68% of its "
        "population) — the third appearance takes the structural "
        "guard, and a question asked by a person is not one."),
    "twelfth_owner_authorization":
        "M6_DECLARATION_AND_GUARD_SCOPE_PROMPT.md, 2026-08-08 — "
        "strictly additive; no bar moved, proven by diff; labels "
        "1y/1z free",
    "label_continuation_convention": (
        "1z exhausts the single-letter scheme. Continuation: a "
        "second series 2a, 2b, ... where every citation carries the "
        "series digit, so 2a cannot be confused with 1a — checked "
        "against every existing label before first use, per the "
        "1k/1n collision lesson."),
    "reflexive_validation_2a": (
        "REFLEXIVE VALIDATION. An instrument commissioned to detect "
        "a defect class is itself a candidate member of that class, "
        "because it operates on exactly the inputs the class is "
        "about. It must be run against the class's seeded corpus "
        "before its first reading is used, and an instrument whose "
        "reflexive validation fails has produced no readings — "
        "every figure it emitted is unestablished. Origin: four "
        "reflexive cases, two FIRED LIVE (the resolver's empty-edge "
        "graph; the census tool's kw_defaults false zero)."),
    "corpus_gates_the_gate_2b": (
        "1z CLARIFIED, additively: the seeded corpus runs against "
        "the detector that ENFORCES — the composed gate as it gates "
        "commits — never against a reference implementation alone. "
        "A corpus-covered shape the gate misses makes the suite's "
        "green a SILENT_PLAUSIBLE_FALLBACK inside the enforcement "
        "machinery (1q verbatim) and the gate "
        "INSTRUMENT_NOT_VALIDATED_AT_CONDITION (1p). Detectors "
        "compose by UNION and are never removed — removal is a "
        "strengthening argument that could quietly be a weakening. "
        "The gate's baseline is a declared allowlist under 1r, "
        "established by a competent enumeration, keyed on file, "
        "symbol and shape — never line numbers."),
    "deferral_condition_2c": (
        "1y's partition carries the contract-deferring distinction "
        "with one condition: a deferring default is exempt only if "
        "the record it defers to is ITSELF a declared contract. "
        "Deferral to another builder dict is the same defect "
        "displaced one hop."),
    "thirteenth_owner_authorization":
        "M6_ENFORCEMENT_CLOSURE_PROMPT.md, 2026-08-08 — strictly "
        "additive; no bar moved, proven by diff; series-2 labels "
        "checked non-confusable",
    "class_scope_2d": (
        "CLASS SCOPE IS NOT NODE SCOPE. The scope of a defect class "
        "is not the scope of the node that discovers it. Narrowing a "
        "class to the discovering node's subject matter is an "
        "exemption under 1r and carries the burden of establishment. "
        "A class may be deferred to a DECLARED node, never "
        "reassigned to a programme that has not accepted it, and "
        "anything downstream of the deferred set carries inherited "
        "pending status until that node runs."),
    "fourteenth_owner_authorization":
        "M6_CLASS_SCOPE_CLOSURE_PROMPT.md, 2026-08-10 — strictly "
        "additive; no bar moved, proven by diff; label 2d free",
    "closure_identity_2e": (
        "CLOSURE IDENTITY. An unreachability discharge names the "
        "closure it was computed against, and that closure carries "
        "an identity: INERT_BY_UNREACHABILITY[closure=<name>@<hash>] "
        "where the hash covers the entry-point set. If the entry "
        "points change, the identity moves and every discharge "
        "computed against the old one is visibly stale rather than "
        "silently wrong. The law-identity chain applied one level "
        "down. A discharge without a closure identity is relative to "
        "nothing and establishes nothing."),
    "fifteenth_owner_authorization":
        "M6_CLOSURE_IDENTITY_PROMPT.md, 2026-08-10 — strictly "
        "additive; no bar moved, proven by diff; label 2e free",
    "provenance_is_a_claim_2f": (
        "PROVENANCE IS A CLAIM. An enumeration of how dispositions "
        "were established is itself subject to instrument-competence "
        "law; produced by reading, its count is a floor under 1x. A "
        "disposition naming no instrument is unestablished as to "
        "provenance regardless of whether its finding stands."),
    "routing_is_not_disposition_2g": (
        "ROUTING IS NOT DISPOSITION. A competence-partitioning "
        "column is derived mechanically from a recorded field "
        "through a mapping declared before application, carries no "
        "dispositional weight, and a shape mapping to no family is a "
        "finding. A family applied by hand to a site is A66 at third "
        "order and a defect."),
    "sixteenth_owner_authorization":
        "M6_LID_ROOF_REPAIR_PROMPT.md, 2026-08-10 — strictly "
        "additive; no bar moved, proven by diff; labels 2f/2g free",
    "join_before_test_2h": (
        "SET-RELATION TRIGGERS JOIN BEFORE THEY TEST. Evaluated "
        "against ledgers as currently dispositioned; the join is an "
        "explicit deliverable, never an assumption; every member in "
        "a difference accounted for individually by NAMED record; a "
        "difference member with no named record stops the node; a "
        "trigger evaluated against a stale snapshot measures refresh "
        "cadence, not the system."),
    "distance_is_residue_2i": (
        "A DISTANCE IS A RESIDUE AND MUST SAY SO. Any figure "
        "reported as a distance states its construction rule "
        "alongside its number and unit — in particular whether "
        "dispositioned members are excluded. A residue may not be "
        "labelled a class size; two figures built on different "
        "construction rules may not be compared for containment "
        "until both rules are stated."),
    "seventeenth_owner_authorization":
        "M6_LID_ROOF_REPAIR_RESUMED_PROMPT.md, 2026-08-10 — strictly "
        "additive; no bar moved, proven by diff; labels 2h/2i free",
    "restriction_not_authorization_2j": (
        "A RESTRICTION IS NOT AN AUTHORIZATION. A clause stating "
        "conditions under which an action is forbidden does not "
        "permit the action when those conditions are absent. "
        "Authority to bank an improvement, lift a suspension or move "
        "a status is stated AFFIRMATIVELY by the owner in the "
        "transmission; absent an affirmative grant, 1c governs. A "
        "filter is not a licence, and attribution performed by the "
        "executor cannot self-authorize what 1c reserves."),
    "repair_supersedes_2k": (
        "REPAIR SUPERSEDES, IT DOES NOT RESTORE. A record suspended "
        "because its computation was produced under a defect is not "
        "un-suspended by repairing the defect; it stands, "
        "permanently, as the record of what was committed. The "
        "repaired quantity is a NEW record, establishing on its own "
        "terms, inheriting no status in either direction, placed "
        "adjacent to the superseded one so the repair is visible by "
        "comparison."),
    "eighteenth_owner_authorization":
        "M6_COMBINED_MANIFEST_PROMPT.md, 2026-08-10 — strictly "
        "additive; no bar moved, proven by diff; labels 2j/2k free",
    "declared_spend_reconciles_2l": (
        "DECLARED SPEND RECONCILES BOTH WAYS. An executor of a "
        "declared spend reconciles declared against executed, per "
        "declared unit, and RAISES on any divergence in either "
        "direction. Under-execution is a coverage gap, never a "
        "saving; over-execution is a declaration failure, never an "
        "efficiency. A completion report issued without that "
        "reconciliation is a plausible in-range result from a "
        "condition the runner could not satisfy — a member of the "
        "class under 1q."),
    "verdict_names_estimate_2m": (
        "A VERDICT NAMES WHAT IT CLEARED AGAINST. A verdict "
        "established or refuted by comparison against an estimated "
        "quantity names that estimate and its identity, the identity "
        "covering the ensemble, seed set and measurement that "
        "produced it. When the estimate is remeasured its identity "
        "moves and every verdict citing the prior identity is stale "
        "by comparison rather than by recollection — the "
        "closure-identity convention applied to verdicts."),
    "nineteenth_owner_authorization":
        "M6_MANIFEST_COMPLETION, 2026-08-10 — strictly additive; no "
        "bar moved, proven by diff; labels 2l/2m free",
    "declaration_reconciles_itself_2n": (
        "A DECLARATION RECONCILES AGAINST ITSELF BEFORE IT "
        "RECONCILES AGAINST EXECUTION. A declared spend stating "
        "both a list and a number is two claims, not one claim "
        "expressed twice. The executor reconciles them against "
        "each other before executing any part of it. A "
        "disagreement stops the node and returns to the declarer; "
        "it is not resolved by preferring the list, nor by "
        "preferring the number, nor by executing the smaller. "
        "Which was intended is knowledge the declarer holds and "
        "the executor does not, and an executor who picks has "
        "performed attribution, which 1c forbids. A declaration "
        "that has not been internally reconciled has not been "
        "received."),
    "control_measures_its_process_2o": (
        "A CONTROL MEASURES THE PROCESS IT RAN IN. A control "
        "executed in a reconstructed process establishes a "
        "property of the code under that reconstruction. It does "
        "not establish what occurred in a process that no longer "
        "exists. Absence of an artifact from a vanished process "
        "is not a reading unless that process emitted its own "
        "control record at the time. Instruments are independent "
        "with respect to a question only if they observe it "
        "independently; instruments that all observe the same "
        "reconstruction are one observation of the reconstruction "
        "and zero observations of the original, however "
        "independent their mechanisms. A run whose output will be "
        "cited as instrument evidence emits its own control "
        "record as its first act."),
    "twentieth_owner_authorization":
        "M6_RENDER_SPEND_DECLARATION launcher, 2026-08-10 — "
        "strictly additive; no bar moved, proven by diff; labels "
        "2n/2o free",
    "count_without_enumeration_2p": (
        "A COUNT WITHOUT AN ENUMERATION IS NOT A DECLARATION. A "
        "declared quantity is received only together with the "
        "enumeration from which it was computed. A bare count "
        "leaves composition to the executor, and an executor who "
        "composes has performed attribution, which 1c forbids. "
        "Where a prior declaration carries a bare count, the "
        "executor drafts the composition and returns it rather "
        "than executing it; the draft takes effect only on the "
        "declarer's affirmative statement per 2j. A count and its "
        "enumeration are reconciled against each other per 2n "
        "before either is acted on."),
    "derived_quantity_committed_2q": (
        "A DERIVED QUANTITY IS COMMITTED AS ITSELF. A node that "
        "solves for a value commits the solved value, not only "
        "its inputs and the solving law. Inputs plus law permit "
        "later re-derivation only where the solve is demonstrably "
        "deterministic in a single pass; a solve whose "
        "intermediate state was overwritten cannot demonstrate "
        "that after the fact. A quantity available only by "
        "re-derivation is a reconstruction and carries the weaker "
        "status 2o assigns to reconstructions, and any claim of "
        "exactness for it states the bound on its error alongside "
        "the value."),
    "twenty_first_owner_authorization":
        "M6_RENDER_SPEND_AMENDED launcher, 2026-08-10 — strictly "
        "additive; no bar moved, proven by diff; labels 2p/2q free",
    "declared_range_reconciles_mechanism_2r": (
        "A DECLARED RANGE IS AN ENVELOPE AND RECONCILES AGAINST THE "
        "REALISED MECHANISM. A spend may be declared as a range only "
        "where its variance is fully determined by a committed law "
        "and carries no executor discretion; the range is stated "
        "together with the law and the quantity that varies. "
        "Reconciliation under 2l is performed against the realised "
        "value and against the mechanism that produced it, per "
        "unit, and never against the envelope. An execution landing "
        "inside the envelope for a reason the law does not account "
        "for is an unreconciled execution and raises. A range with "
        "any discretionary component is not a declaration and is "
        "returned to the declarer under 2n."),
    "twenty_second_owner_authorization":
        "M6_RECALIBRATION_EXECUTE launcher (complete retransmission), "
        "2026-08-10 — strictly additive; no bar moved, proven by "
        "diff; label 2r free",
    "unexecutable_component_stops_2s": (
        "AN UNEXECUTABLE DECLARED COMPONENT STOPS THE SPEND. A "
        "declared component discovered mid-execution to be "
        "unexecutable stops the execution and returns to the "
        "declarer, whether or not the executor judges it severable "
        "from the remainder. Severability is a claim about the "
        "declaration's structure and belongs to its author; an "
        "executor who severs has performed attribution, which 1c "
        "forbids. Work already executed under the declaration "
        "stands and reconciles normally per 2l; work not yet "
        "executed waits. The cost of returning is one transmission, "
        "and an executor pricing that cost prices it against the "
        "run actually in progress, not against an uninterrupted "
        "ideal run that no longer exists."),
    "twenty_third_owner_authorization":
        "M6_CONTROL_COMPLETION launcher, 2026-08-10 — strictly "
        "additive; no bar moved, proven by diff; label 2s free",
    "declarer_count_is_recollection_2t": (
        "A DECLARER'S COUNT IS A RECOLLECTION UNTIL AN INSTRUMENT "
        "ESTABLISHES IT. A count, enumeration or population figure "
        "appearing in a declaration or a ruling without the "
        "instrument that produced it is the declarer's recollection "
        "and carries no weight. The executor establishes it before "
        "acting on it and reports the established value against the "
        "recollected one. A recollection that survives establishment "
        "is recorded as confirmed; one that does not is superseded "
        "per 2k in the ruling and in every record that inherited it. "
        "This clause binds the declarer symmetrically with the way "
        "2f binds the executor, and an executor who acts on an "
        "unestablished declarer figure has adopted a reading, which "
        "1s forbids."),
    "contract_sentence_is_a_claim_2u": (
        "A CONTRACT SENTENCE IS A COMMITTED CLAIM. Prose in a "
        "committed instrument that states a property of that "
        "instrument is a claim subject to the same law as a numeric "
        "record. On refutation it is superseded in place per 2k: "
        "the original sentence retained and marked, the refuting "
        "evidence named adjacent, never silently edited and never "
        "left standing bare. Superseding such a sentence changes no "
        "behaviour, moves no bar and alters no computation; it is a "
        "supersession and not a repair, and does not require a "
        "declared repair-scope node."),
    "twenty_fourth_owner_authorization":
        "M6_CONTRACT_AND_FLOOR_CONDITION launcher, 2026-08-11 — "
        "strictly additive; no bar moved, proven by diff; labels "
        "2t/2u free",
    "unestablished_finding_may_not_reorder_2v": (
        "AN UNESTABLISHED FINDING MAY STOP WORK BUT MAY NOT REORDER "
        "IT. A finding not yet established may halt execution that "
        "depends on it, because halting is reversible and its cost "
        "is one transmission. It may not reorder the programme, "
        "promote a node, demote a node, or redirect a declared "
        "sequence, because reordering commits work under a premise "
        "that has not been demonstrated. Establishment precedes any "
        "change to sequence. A sequence changed under a finding "
        "that does not survive establishment is restored to its "
        "prior order and the restoration is recorded per 2k. This "
        "clause binds the declarer, who is the only party able to "
        "reorder."),
    "twenty_fifth_owner_authorization":
        "M6_ERA_STABILITY_AND_DEGENERACY launcher, 2026-08-11 — "
        "strictly additive; no bar moved, proven by diff; label 2v "
        "free",
    "identity_requires_committed_recipe_2w": (
        "AN IDENTITY WITHOUT A COMMITTED RECIPE IS NOT AN IDENTITY. "
        "A hash committed as a record's identity is committed "
        "together with the recipe that produced it: the payload's "
        "construction and its serialization, in the same act. An "
        "identity that cannot be recomputed from committed records "
        "names nothing mechanically — it is comparable only to "
        "itself, no instrument can detect that it moved, and any "
        "assertion that it moved or did not is recollection. "
        "Minting a replacement does not repair it: per 2k the "
        "original stands as the record of what was committed, with "
        "its coverage recorded as undeterminable and the bounded "
        "reconstruction attempt recorded as the evidence for that; "
        "the replacement is a new identity establishing on its own "
        "terms, whose authority begins at minting and does not "
        "reach backward. A mechanism whose guarantee depends on "
        "comparing identities is inoperative wherever either "
        "identity is non-recomputable, and says so where it is "
        "cited."),
    "twenty_sixth_owner_authorization":
        "M6_IDENTITY_RECIPE_CENSUS launcher, 2026-08-11 — strictly "
        "additive; no bar moved, proven by diff; label 2w free",
    "identity_covers_one_thing_2x": (
        "AN IDENTITY COVERS ONE THING. Where a record's freshness "
        "depends on several independently varying things — the "
        "quantity, the instrument that measured it, the conditions "
        "it was measured under — each is carried by its own "
        "identity and evaluated separately. A single identity over "
        "a composite payload answers only whether something moved "
        "and not what moved, while the remedies for the components "
        "differ, so collapsing them discards the distinction the "
        "citing path needs. A citing path reports which identities "
        "moved. A state in which one moved and another did not is "
        "a finding named in its own right; it is never reported as "
        "unchanged, and never reported as stale without naming "
        "which."),
    "twenty_seventh_owner_authorization":
        "M6_IDENTITY_REMEDIATION launcher, 2026-08-11 — strictly "
        "additive; no bar moved, proven by diff; label 2x free",
    "specification_not_recoverable_from_consequences_2y": (
        "A SPECIFICATION IS NOT RECOVERABLE FROM ITS CONSEQUENCES. "
        "Where a lost record is a declaration — a chosen "
        "specification rather than a measured quantity — it is not "
        "reconstructed by finding a candidate that reproduces the "
        "committed outputs, however over-determined the "
        "reproduction. The outputs establish which specifications "
        "are consistent with them; they never establish that the "
        "specification was correct, and correctness is the property "
        "the lost record carried. The remedy is a fresh "
        "declaration, authored and reviewed now, with dependent "
        "records re-established forward under it and never "
        "restored. A candidate that reproduces the old outputs may "
        "be compared against the fresh declaration afterwards as a "
        "cross-check, and a disagreement is a finding; it may never "
        "stand in place of the fresh declaration."),
    "failed_reconstruction_is_about_the_attempt_2z": (
        "A FAILED RECONSTRUCTION IS A STATEMENT ABOUT THE ATTEMPT "
        "UNTIL THE SEARCH SPACE IS JUSTIFIED. A bounded "
        "reconstruction that fails to reproduce a committed "
        "identity establishes that the attempted payloads do not "
        "produce it. It does not establish that the identity is "
        "non-recomputable. Before an identity is placed in the "
        "non-recomputable column, the attempt cites the producing "
        "code and states which payload that code would have "
        "constructed and why the search space covered it. Where "
        "the producing code is unavailable, that unavailability is "
        "the finding recorded, rather than non-recomputability. A "
        "non-match is a property of the attempt until shown "
        "otherwise."),
    "twenty_eighth_owner_authorization":
        "M6_CLOSURE_REDECLARATION launcher, 2026-08-11 — strictly "
        "additive; no bar moved, proven by diff; labels 2y/2z free",
    "closure_named_by_direction_3a": (
        "A CLOSURE IS NAMED BY ITS DIRECTION. A reachability finding "
        "is a statement about one traversal from one entry set in "
        "one direction. Its disposition carries the identity of that "
        "closure. An unqualified reachability status is a claim "
        "about the system, and no single closure establishes one; a "
        "system-level status requires agreement across every "
        "declared closure whose direction could reach the site. "
        "Where only one closure exists, the honest status is "
        "qualified, not bare. Rationale: A61 established that "
        "realization calls flow toward powder code, so a "
        "measurement-rooted import graph structurally cannot observe "
        "them. The defect is not in the traversal — it is in a label "
        "that omits the direction and thereby promotes a local "
        "reading into a global one."),
    "twenty_ninth_owner_authorization":
        "M6_REALIZATION_CLOSURE launcher, 2026-08-11 — strictly "
        "additive; no bar moved, proven by diff; label 3a free",
    "fragment_is_caution_not_instruction_3b": (
        "A FRAGMENT MAY BE ADOPTED AS CAUTION BUT NEVER CITED AS "
        "INSTRUCTION. A transmission received incomplete confers no "
        "authority (A118). Where a fragment is purely restrictive, "
        "the executor may adopt it as self-imposed caution, recorded "
        "with the fragment named as origin and marked "
        "NOT_RECEIVED_AS_RULING. So marked it may govern the "
        "executor's conduct and may not be cited by any path, quoted "
        "as law, or relied upon by another node. The whole "
        "transmission supersedes it in place on arrival; if the "
        "whole transmission does not contain it, the caution lapses. "
        "Rationale: discarding a seen restriction requires un-seeing "
        "it, which no executor can do honestly. Holding it as a "
        "ruling would let a rule no declarer issued acquire citable "
        "authority. The distinction that resolves both is "
        "provenance, not content."),
    "thirtieth_owner_authorization":
        "M6_INERT_SEMANTICS launcher, 2026-08-11 — strictly "
        "additive; no bar moved, proven by diff; label 3b free",
    "baseline_superseded_with_a_reason_3c": (
        "A BASELINE IS NOT REFRESHED, IT IS SUPERSEDED WITH A "
        "REASON. Where a gate's baseline is keyed to something that "
        "code movement can change, no operation may exist that "
        "brings the baseline into agreement with the code without a "
        "stated reason. Each changed key is dispositioned by the "
        "mover as cosmetic, changed, or removed, and the "
        "disposition is recorded with the movement. A baseline "
        "brought into agreement without a reason records only that "
        "somebody wanted the gate quiet. Rationale: line-keyed "
        "allowlists were refreshed mechanically four times across "
        "this programme. The key's fragility made the refresh "
        "frequent; the refresh's cheapness made the fragility "
        "survivable. Precision in the key is only sustainable if "
        "responding to it costs a sentence, and a gate is only "
        "load-bearing if silencing it costs one too."),
    "thirty_first_owner_authorization":
        "M6_ALLOWLIST_KEY_SEMANTICS launcher, 2026-08-11 — strictly "
        "additive; no bar moved, proven by diff; label 3c free",
    "proof_establishes_only_its_invariant_3d": (
        "A PROOF ESTABLISHES ONLY ITS OWN INVARIANT. Where a claim "
        "rests on a premise its instrument does not check, the "
        "premise is named in the record and either checked by a "
        "second instrument or carried explicitly as unestablished. A "
        "claim is citable at the strength of its weakest checked "
        "premise, not at the strength of its conclusion. A premise "
        "held true by the author's knowledge of the circumstances is "
        "unchecked, however certain the author is. Rationale: the "
        "A183 migration was proven cosmetic by a distribution "
        "invariant that cannot see an in-place edit. The conclusion "
        "held, carried by a fact the author knew and the instrument "
        "never tested. The defect is not the wrong answer — there "
        "was none — it is that the record would have read "
        "identically had the answer been wrong."),
    "thirty_second_owner_authorization":
        "M6_PROOF_PREMISE launcher, 2026-08-11 — strictly additive; "
        "no bar moved, proven by diff; label 3d free",
    "floor_is_a_bound_3e": (
        "A FLOOR IS A BOUND, AND A BOUND MAY ONLY TIGHTEN. Where a "
        "threshold is derived from repeated measurement, its "
        "declaration must state its kind. A quantity declared BOUND "
        "is combined across ensembles by taking the worst observed "
        "excursion, and may move only in the conservative direction "
        "as ensembles accumulate. A quantity declared ESTIMATE is "
        "combined by a rule declared before the second ensemble is "
        "run, and may move in either direction. A quantity with no "
        "declared kind may not be used in a gate. A combining rule "
        "chosen after the measurements it combines is admissible "
        "only where every candidate rule LEGALLY AVAILABLE UNDER THE "
        "LAW IN FORCE AT THE MOMENT OF CHOICE yields the same "
        "disposition. Availability is a property of the law, not of "
        "the executor's enumeration: a candidate the law already "
        "forbade is not made available by being named, and a "
        "candidate the law permitted is not made unavailable by a "
        "refusal issued afterwards. The record must name each "
        "candidate, state for each whether it was available and "
        "under which prior ruling, and record the agreement across "
        "the available set as the reason for admissibility."),
    "thirty_third_owner_authorization":
        "M6_PROXY_VS_TEST launcher, 2026-08-11 — strictly additive; "
        "no bar moved, proven by diff; label 3e free",
    "refuted_bound_leaves_no_bound_3f": (
        "A REFUTED BOUND LEAVES NO BOUND. The refutation of a claimed "
        "ordering between two quantities establishes that the ordering "
        "fails where it was tested. It does not establish the converse "
        "ordering, at that instance or at any other. Until an ordering "
        "is separately established, the quantities are unordered, and "
        "every disposition depending on their order must be computed "
        "rather than inferred. An ordering asserted in the "
        "conservative direction is subject to the same requirement as "
        "one asserted in the permissive direction; the direction of an "
        "unchecked premise does not bear on whether it has been "
        "checked."),
    "thirty_fourth_owner_authorization":
        "M6_REFUTED_BOUND launcher, 2026-08-11 — strictly additive; no "
        "bar moved, proven by diff; label 3f free",
    "discriminator_validated_against_factor_space_3g": (
        "A DISCRIMINATOR IS VALIDATED AGAINST THE FACTOR SPACE, NOT "
        "AGAINST THE EXPLANATIONS NAMED. Before an observation is "
        "relied upon to discriminate between competing explanations, "
        "the factors capable of producing the observed pattern must be "
        "enumerated as a product of the design's dimensions, and the "
        "observation must be shown to separate them. An observation "
        "that distinguishes the explanations that happened to be "
        "named, while leaving two or more factors of the product "
        "entangled, does not discriminate. Where the existing design "
        "cannot separate the factors, the discriminating work is the "
        "computation of the design's empty cells, and no diagnosis may "
        "be named until they are computed or their absence is recorded "
        "as a limit on what can be concluded."),
    "thirty_fifth_owner_authorization":
        "M6_CONFOUNDED_DISCRIMINATOR launcher, 2026-08-11 — strictly "
        "additive; no bar moved, proven by diff; label 3g free",
    "a_qualifier_has_a_domain_3h": (
        "A QUALIFIER HAS A DOMAIN. Every derived classification "
        "carries a domain condition — the precondition under which "
        "the thing it classifies exists at all. The domain condition "
        "must be stated when the classification is declared and "
        "checked before any value is assigned. A classification "
        "applied outside its domain yields a value that has the form "
        "of a finding and the content of none. Enlarging a "
        "classification's value set does not address its domain: a "
        "dimension may be inapplicable rather than merely unmeasured, "
        "and inapplicability is not a band."),
    "thirty_sixth_owner_authorization":
        "M6_UNITS_CLASS_CHECK launcher, 2026-08-11 — strictly "
        "additive; no bar moved, proven by diff; label 3h free",
    "underdetermined_term_filled_by_ruling_3i": (
        "AN UNDERDETERMINED TERM IS FILLED BY RULING, NOT BY "
        "IMPLEMENTATION. Where a law's text does not determine a "
        "quantity to a single computable value, the choice among the "
        "remaining candidates is an act of lawmaking. It must be "
        "escalated and ruled before it is implemented. An "
        "implementation that resolves such an ambiguity silently has "
        "amended the law without authorization, and every result "
        "computed under it is a statement about the quantity actually "
        "computed and not about the quantity the law names, however "
        "faithfully the implementation was reasoned. The obligation "
        "attaches at the moment the implementer notices more than one "
        "defensible reading, and noticing is not required for the "
        "obligation to have been breached."),
    "law_vocabulary_is_the_enumeration_set_3j": (
        "THE LAW'S VOCABULARY IS THE ENUMERATION SET. A sweep for "
        "terms a law names but does not determine is enumerated from "
        "the law corpus's own vocabulary, not from the "
        "implementation's surface. The law corpus is finite and "
        "identified; the implementation surface is neither. For each "
        "named term the sweep states whether an executable choice was "
        "required, what choice was made, where it is made, and under "
        "whose authority. A term found to have been pinned by "
        "implementation is escalated under 3i before any further "
        "result cites it. A sweep enumerated from the law side has a "
        "stateable boundary and terminates; one enumerated from the "
        "code side has neither and may not be relied upon to have "
        "been complete."),
    "determination_as_stable_as_its_artifact_3k": (
        "A DETERMINATION IS ONLY AS STABLE AS THE ARTIFACT THAT CARRIES "
        "IT. A term whose meaning is fixed only by an artifact outside "
        "the identity chain is determined in fact and undetermined in "
        "law. Such a term must be ratified into the hashed corpus — by "
        "quotation, with the introducing commit and date, so that the "
        "ratification records when the determination was made rather "
        "than redating it — before any further result cites it. The "
        "defect is not that the artifact is wrong. It is that the "
        "artifact can change without the identity moving, and so a "
        "result citing it cannot be shown to have cited what it cited. "
        "Correctness of the unhashed artifact is not a defence; an "
        "unhashed artifact that happens to say the right thing is "
        "indistinguishable, from inside the corpus, from one that has "
        "been edited. Where a sweep reports on determination, it "
        "reports the artifact and whether the artifact is inside the "
        "identity, as separate facts. 'Determined' alone is not a "
        "finding."),
    "instrument_declares_its_extent_3l": (
        "AN INSTRUMENT DECLARES ITS EXTENT, AND ITS VERDICT IS HONOURED "
        "ONLY WHEN THE EXTENT IS MET AND ITS REFUSAL HAS BEEN "
        "DEMONSTRATED. An instrument whose failure mode is silence "
        "cannot be trusted by its verdict alone, because the verdict "
        "channel does not carry the difference between a check that ran "
        "and a check that was not there. Every gate therefore declares "
        "its expected extent as an ENUMERATION, not as a count — a "
        "count without an enumeration is not a declaration (2p), and a "
        "floor of 'at least N' is satisfied by N from the wrong "
        "targets. An unmet extent is a REFUSAL rather than a pass. "
        "Extent is checked in BOTH directions: a declared element "
        "missing is a refusal, and an undeclared element present is a "
        "refusal, because extent can be lost by disappearance and "
        "gained by accident and a gate that checks one direction cannot "
        "tell you its declared list is still the list being run. A GATE "
        "THAT HAS NEVER REFUSED IS UNPROVEN: before a gate's pass is "
        "cited as evidence, it must have been made to refuse, once per "
        "clause it asserts, and the refusal recorded with its date. "
        "Where a comparison is the instrument, its extent is bounded by "
        "the extent of its subject; a comparison wider than what it "
        "compares reports a difference belonging to something else."),
    "a_pass_carries_its_extent_3m": (
        "A PASS CARRIES ITS EXTENT, AND ANY LENIENCY IS FINITE AND "
        "CONSUMED. An instrument's verdict may not be read wider than "
        "the extent over which it was taken. The extent therefore "
        "TRAVELS WITH THE VERDICT, in the artifact, so that a reader "
        "who has only the artifact cannot mistake a narrow pass for a "
        "wide one. A gate whose declared extent falls short of the "
        "obligation it stands for is permitted, provided the shortfall "
        "is STATED IN THE ARTIFACT and not left to be inferred. Where "
        "an instrument makes an allowance for a known instability, "
        "that allowance is registered by identity, is finite, and is "
        "consumed on use. An allowance that is unregistered, that is "
        "registered without a remaining count, or that is exhausted, "
        "is a REFUSAL. Being known about is not relief. An assertion "
        "that something cannot be tested is an assertion about the "
        "test space and carries the same evidential burden as any "
        "other; untested, it is UNCHECKED, not IMPOSSIBLE."),
    "a_control_without_a_miss_record_3n": (
        "A CONTROL THAT LEAVES NO RECORD OF ITS MISSES CANNOT ESTABLISH "
        "ITS OWN SUFFICIENCY. A control is measured by what it WOULD "
        "HAVE CAUGHT, not by what it caught. Where a control's failures "
        "produce no artifact, its record of successes is not evidence "
        "of its coverage, however long that record runs, and its "
        "sufficiency is UNCHECKED rather than established. A newly "
        "built instrument is therefore tested against the register of "
        "previously recorded defect classes, by deliberate attempt to "
        "make it exhibit each class WHILE REPORTING A PASS. The "
        "adversary is the register and not the builder's imagination, "
        "because the builder's imagination is the thing under test. "
        "Each such attempt is itself proven able to fire against a "
        "mutated instrument, and one that cannot is discarded rather "
        "than counted. The register that determines which attempts are "
        "required determines the instrument's admissibility, and is "
        "therefore hashed."),
    "a_refusal_is_evidence_of_what_it_names_3o": (
        "A REFUSAL IS EVIDENCE ONLY OF WHAT IT NAMES. A control's "
        "refusal counts as detection of a condition only where the "
        "refusal NAMES that condition, and where the naming has been "
        "shown to DISCRIMINATE — distinct conditions producing distinct "
        "reasons. A refusal whose named cause does not match the "
        "condition under test credits the control with a detection it "
        "did not make, and the attempt is recorded ATTEMPT_NOT_EXECUTED "
        "rather than CAUGHT. The witness for an attempt is the "
        "instrument's own named output, not the harness's setup, "
        "because a chain of assurances about the setup has no "
        "termination while the instrument's output is a single "
        "artifact. Preconditions on the setup are permitted where they "
        "are direct observations and are not relied upon where they are "
        "actions. Where a control is repaired, the repair is a NEW "
        "INSTRUMENT and is subject to the same demonstration as the "
        "original."),
    "an_absent_defect_is_not_a_guarded_defect_3p": (
        "AN ABSENT DEFECT IS NOT A GUARDED DEFECT, AND AN UNRETAINED "
        "CAPTURE IS NOT A RECORD. Where a hostile attempt finds a defect "
        "structurally absent, the absence is a property of the "
        "implementation as it stands and is loseable by any later edit "
        "with nothing to observe the loss. The mutation that "
        "reintroduces the defect is therefore RETAINED AS A STANDING "
        "CONTROL, and the immunity is recorded as STRUCTURAL or "
        "CONTINGENT. An absence for which no reintroducing mutation can "
        "be constructed is UNGUARDED_IMMUNITY and is a WEAKER result "
        "than a detection, not a stronger one. Where an observation is "
        "captured to a path that the next run overwrites, the capture "
        "serves the present question and destroys the series; where a "
        "record is required, RETENTION IS PART OF THE CAPTURE, and a "
        "question that becomes unanswerable through loss of record is "
        "recorded as unanswerable rather than reconstructed by "
        "inference."),
    "a_check_observes_only_when_it_runs_3q": (
        "A CHECK OBSERVES ONLY WHEN IT RUNS, AND PROTECTION FOLLOWS "
        "STAKES RATHER THAN EXECUTION. A check invoked once observes "
        "the state at the moment of invocation and is silent about "
        "every change after it. Where the subject can change "
        "afterwards, the check is RETAINED and runs on the path capable "
        "of changing it. A one-shot invocation is DIAGNOSTIC; it is not "
        "evidence about any state other than the one it saw. The set of "
        "artifacts a control protects is determined by what cited "
        "results depend upon, not by what the execution path happens to "
        "read. An artifact that determines a result is protected even "
        "where no code reads it, and the absence of a reader is not "
        "evidence of low stakes — it is the reason the exposure is "
        "invisible. Where an artifact must remain changeable, it is "
        "bound by DIGEST rather than by identity, and the digest is "
        "bound by the identity, so that change remains possible and "
        "silent change does not."),
    "an_enumeration_is_certified_by_its_complement_3r": (
        "AN ENUMERATION IS CERTIFIED BY ITS COMPLEMENT, AND AN UNDERIVED "
        "EXPECTATION IS NOT STATED. The count an enumeration returns "
        "cannot establish the extent over which it was taken, because an "
        "under-wide extent returns a count of the same shape as a "
        "correct one. An enumeration is therefore certified by "
        "enumerating what its pattern EXCLUDES and showing the excluded "
        "set contains nothing of the kind being counted. The "
        "complement's size and a sample of it are reported alongside the "
        "count. Where a value is expected in advance, it is stated only "
        "if it is DERIVABLE. A guessed expectation becomes the shape "
        "against which the result is checked, and a result that matches "
        "a guess is not thereby checked. This binds the party directing "
        "the work as much as the party performing it, and more so, "
        "because a direction carries the weight of an instruction."),
    "a_measure_must_discriminate_3s": (
        "A MEASURE MUST DISCRIMINATE THE CHANGE IT CERTIFIES, AND A "
        "COMPLEMENT IS CLASSIFIED RATHER THAN REPORTED. A check cited "
        "as evidence that something did not change must report a "
        "property that WOULD DIFFER had it changed. A correctly "
        "computed value that is constant across the conditions it is "
        "meant to separate certifies nothing, and its constancy is "
        "indistinguishable from the constancy of the thing it observes. "
        "Where a selection is made by a proxy, the members the proxy "
        "EXCLUDES are classified rather than merely enumerated: each "
        "kind present in the complement carries a stored disposition, "
        "and a kind appearing without one HALTS the selection until it "
        "is classified. Reporting a complement to a reader is not a "
        "control, because it depends on a reader noticing; classifying "
        "it is, because a new kind cannot pass without a decision."),
    "a_decision_needs_a_review_surface_3t": (
        "A DECISION IS CONFIRMED ONLY WHERE A SURFACE COULD HAVE SHOWN "
        "IT, AND A RECORD MAY NOT ATTRIBUTE TO AN ACTOR WHAT NO SURFACE "
        "OFFERED THAT ACTOR."),
    "a_surface_is_a_declared_selection_3u": (
        "A SURFACE IS A DECLARED SELECTION, AND AN OMISSION THAT STATES "
        "NO REASON IS INDISTINGUISHABLE FROM A LAPSE."),
    "which_act_governs_must_be_stated_3v": (
        "A RECORD MAY ACCUMULATE ACTS, BUT WHICH ACT GOVERNS MUST BE "
        "STATED RATHER THAN INFERRED FROM ORDER."),
    "an_act_carries_its_route_3w": (
        "AN ACT CARRIES ITS ROUTE, AND A COUNT THAT MIXES ROUTES "
        "MEASURES THE PROCESS RATHER THAN THE SUBJECT."),
    "a_change_is_scoped_by_its_dependents_3x": (
        "A CHANGE TO A SHARED THING IS SCOPED BY ITS DEPENDENTS, AND AN "
        "UNENUMERATED DEPENDENT SET IS AN UNDECLARED SCOPE."),
    "a_citation_confers_authority_only_if_it_resolves_3y": (
        "A CITATION CONFERS AUTHORITY ONLY WHERE THE CITED ARTIFACT "
        "EXISTS, AND AN UNRESOLVABLE REFERENCE CREATES NO OBLIGATION."),
    "a_record_of_a_refusal_is_not_subject_to_it_3z": (
        "A RECORD OF A REFUSAL IS NOT SUBJECT TO THE REFUSAL IT "
        "RECORDS, PROVIDED IT CHANGES NOTHING THE REFUSAL GOVERNS. "
        "Narrow and not a bypass: it licenses a RECORD_ONLY commit, "
        "whose diff touches ONLY record paths — no service, no test, no "
        "instrument, no configuration. Such a commit STILL RUNS THE "
        "FULL GATE; it does not skip it, and it lands CARRYING the "
        "refusal verbatim in its own message, so the refusal is "
        "recorded rather than evaded."),
    "a_derived_quantity_carries_its_inputs_3aa": (
        "A DERIVED QUANTITY CARRIES THE IDENTITY OF EVERY INPUT IT "
        "READ AND OF THE DERIVATION THAT PRODUCED IT, OR IT IS NOT "
        "EVIDENCE."),
    "fifty_seventh_owner_authorization":
        "PALT_D5_COLOUR_SPACE_BUNDLE launcher, 2026-08-13 — ONE entry "
        "covering the whole bundle, not one per file touched, and "
        "protocol_identity moves ONCE. Granted for the hashed-amendment "
        "route on COLOUR_AUTHORITY, whose pan_shades line had been left "
        "stale by the shade-authority record at 6341794 and was flagged "
        "rather than fixed then. Landing with it: the colour-space fix "
        "at the engine boundary by recommendation (e) — the space rides "
        "on the AUTHORITY, which is already digested by "
        "material_identity(), so ZERO material identities move and the "
        "frozen builder is untouched — and the digest binding of "
        "COLOUR_SPACE_BY_AUTHORITY, without which the mapping would be "
        "an undigested input to a value a rendered frame depends on. "
        "Bundled deliberately: every identity move is a separate "
        "reproducibility break and two breaks where one would do is a "
        "self-inflicted cost. No bar moved. D5 stays open",
    "a_label_naming_a_condition_does_not_create_it_3ab": (
        "A LABEL NAMING A CONDITION DOES NOT CREATE IT, AND A "
        "TRANSMISSION ADDRESSED TO A STATE THE RECIPIENT IS NOT IN "
        "ASSERTS THAT STATE FALSELY."),
    "fifty_sixth_owner_authorization":
        "PALT_M6_TWO_MEASUREMENTS launcher, 2026-08-13 — strictly "
        "additive; no bar moved; label 3ab free. Landed ALONE, with no "
        "instrument, under the A533 exception the launcher states "
        "explicitly at A586: 3ab governs TRANSMISSIONS rather than "
        "code, so no instrument can exist for it and A533's "
        "law-behind-its-instrument rule has no subject. Drafted at "
        "A567 after a launcher headed FOR A FRESH SESSION was delivered "
        "to the same session with less context than when it first "
        "declined",
    "fifty_fifth_owner_authorization":
        "PALT_M6_PROVENANCE_INSTRUMENT_AND_RECOMPUTE launcher, "
        "2026-08-12 — strictly additive; no bar moved; label 3aa free. "
        "Landed BEHIND its instrument, not ahead of it (A533/A560): "
        "palette_powder_texture_axes.measure_texture_axes seals A558 "
        "(a)-(e) as its first statement and has one return carrying "
        "_provenance unconditionally, with eight refusal probes "
        "observed firing (a559_provenance_refusal_demonstration.json). "
        "Hashing 3aa over an instrument that did not yet do what 3aa "
        "names is the error the previous issue of this node was "
        "deferred to avoid",
    "fifty_fourth_owner_authorization":
        "PALT_M6_CELL_PROVENANCE launcher, 2026-08-12 — strictly "
        "additive; no bar moved; label 3z free; RECORD_ONLY defined and "
        "fenced by a standing control",
    "fifty_third_owner_authorization":
        "PALT_M6_FRAME_INVENTORY launcher, 2026-08-12 — strictly "
        "additive; no bar moved; label 3y free; register to twenty-two",
    "fifty_second_owner_authorization":
        "PALT_M6_MATTE_TEXTURE_FRAMES launcher, 2026-08-12 — strictly "
        "additive; no bar moved; label 3x free; register to twenty-one; "
        "node STOPPED at A475, nothing rendered",
    "fifty_first_owner_authorization":
        "PALT_M4C_8 launcher, 2026-08-12 — strictly additive; no bar "
        "moved, proven by size AND digest; label 3w free; register to "
        "twenty, minted only after both distinctness directions held",
    "fiftieth_owner_authorization":
        "PALT_M4C_7 launcher, 2026-08-12 — strictly additive; no bar "
        "moved, proven by size AND digest; label 3v free; register to "
        "nineteen; class ten EXHIBITED at apply_confirmations",
    "forty_ninth_owner_authorization":
        "PALT_M4C_6 launcher, 2026-08-12 — strictly additive; no bar "
        "moved, proven by size AND digest; label 3u free; register to "
        "eighteen; REQUIRED_PANEL_ROWS ruled NOT authoritative",
    "forty_eighth_owner_authorization":
        "PALT_M4C_5 launcher, 2026-08-12 — strictly additive; no bar "
        "moved, proven by size AND digest; label 3t free; register to "
        "seventeen; shade_names marked CONFIRMED_WITHOUT_REVIEW_SURFACE "
        "on task 9, not withdrawn",
    "forty_seventh_owner_authorization":
        "M6_RECORD_SCOPE launcher, 2026-08-12 — strictly additive; no "
        "bar moved, proven by size AND digest; label 3s free; register "
        "to sixteen; extension proxy retained, complement classified",
    "forty_sixth_owner_authorization":
        "M6_RATIFICATION_BACKLOG launcher, 2026-08-12 — strictly "
        "additive; no bar moved, proven by diff; label 3r free; A387 "
        "guard admitted under A384's exception; register to fifteen",
    "forty_fifth_owner_authorization":
        "M6_RECORD_INTEGRITY launcher, 2026-08-12 — strictly additive; "
        "no bar moved, proven by diff; label 3q free; record set becomes "
        "DIGEST_BOUND; register grows to fourteen classes",
    "forty_fourth_owner_authorization":
        "M6_ABSENT_VS_GUARDED launcher, 2026-08-12 — strictly additive; "
        "no bar moved, proven by diff; label 3p free; register grows to "
        "thirteen classes; fifth disposition DEFECT_STRUCTURALLY_ABSENT",
    "forty_third_owner_authorization":
        "M6_EXHIBITED_REPAIR launcher, 2026-08-12 — strictly additive; "
        "no bar moved, proven by diff; label 3o free; eighth hashed "
        "block EXTENT_DIGESTS added; register grows to twelve classes",
    "forty_second_owner_authorization":
        "M6_HOSTILE_CONTROL launcher, 2026-08-12 — strictly additive; "
        "no bar moved, proven by diff; label 3n free; seventh hashed "
        "block DEFECT_CLASS_REGISTER added, append-only",
    "forty_first_owner_authorization":
        "M6_EXTENT_VS_OBLIGATION launcher, 2026-08-12 — strictly "
        "additive; no bar moved, proven by diff; label 3m free; TIER_2 "
        "added with AMBER as a distinct non-pass artifact value",
    "fortieth_owner_authorization":
        "M6_GATE_EXTENT launcher, 2026-08-11 — strictly additive; no bar "
        "moved, proven by diff; label 3l free; guarded_commit.sh gains "
        "A315's four clauses and nothing else",
    "thirty_ninth_owner_authorization":
        "M6_HASHED_AUTHORITY launcher, 2026-08-11 — strictly additive; "
        "no bar moved, proven by diff; label 3k free; new hashed block "
        "DENOMINATOR_CONVENTION added, PASS_LAW untouched",
    "thirty_eighth_owner_authorization":
        "M6_LAW_VOCABULARY_SWEEP launcher, 2026-08-11 — strictly "
        "additive; no bar moved, proven by diff; label 3j free",
    "thirty_seventh_owner_authorization":
        "M6_UNDERDETERMINED_TERM launcher, 2026-08-11 — strictly "
        "additive; no bar moved, proven by diff; label 3i free",
}

#: 3k — ratified from an artifact that was outside the identity chain.
#: Quotation, not restatement: the determination dates to 2026-08-07,
#: before measurement, and a restatement would silently redate it to
#: the day of ratification and forfeit the predeclaration.
DENOMINATOR_CONVENTION = {
    "term": "relative_effect denominator",
    "determination": "MEAN_OF_THE_TWO_VALUES",
    "ratified_from": ("palette_material_swatch.py, comment adjacent to "
                      "MINIMUM_RELATIVE_EFFECT"),
    "introducing_commit": "48f6bd4",
    "introducing_date": "2026-08-07",
    "quoted_text": ("Relative effect size required on an axis for it to "
                    "count as discriminating: the two materials must "
                    "differ by at least this fraction of their mean on "
                    "that axis. Predeclared."),
    "status_before_ratification":
        "DETERMINED_IN_FACT_UNDETERMINED_IN_LAW",
    "ratification_changes_meaning": "NO",
    "single_reading_confirmed": (
        "'their' has one plural referent (the two materials); 'on that "
        "axis' excludes a mean across axes; no seed language is present "
        "so a mean across seeds is excluded — exactly one reading"),
}


#: 3n — the seventh hashed block. This register determines which
#: hostile attempts a new instrument must survive, therefore it
#: determines that instrument's admissibility, therefore it determines
#: every result that cites it. Under 3k an artifact with that role
#: cannot sit where it can be edited without protocol_identity()
#: moving. APPEND ONLY: a correction is a new entry citing the old.
DEFECT_CLASS_REGISTER = {
    "SILENT_EXTENT_LOSS": {
        "definition": ("a check whose failure mode is collecting "
                       "nothing, read through a channel that cannot "
                       "distinguish 'ran and passed' from 'did not run'"),
        "first_instance": "test_characterization_protocol.py at 0 bytes",
        "second_instance": ("a census glob written non-recursively: "
                            "*.json returns 99 where **/*.json returns "
                            "1638, and both are equally count-shaped. "
                            "Locus is enumeration, not test collection "
                            "— same class, per A392's register "
                            "discipline against near-duplicates"),
        "commit": "c394e62", "date": "2026-08-11",
        "found_by": "FOUND_BY_FIRING"},
    "CURE_CARRYING_THE_DISEASE": {
        "definition": ("a remedy whose own implementation instantiates "
                       "the failure class it was written to prevent"),
        "first_instance": "the A315 extent gate waivable by one env var",
        "commit": "a52b6a5", "date": "2026-08-11",
        "found_by": "FOUND_BY_ADJUDICATION"},
    "EXTENT_OF_COMPARISON_EXCEEDING_EXTENT_OF_SUBJECT": {
        "definition": ("a comparison wider than its subject reports a "
                       "difference belonging to something else"),
        "first_instance": "four comment lines compared to a three-line comment",
        "commit": "d95e569", "date": "2026-08-11",
        "found_by": "FOUND_BY_FIRING"},
    "REPORT_BEFORE_CLASSIFY": {
        "definition": ("a raw match count reported, or acted on, before "
                       "each candidate has been classified"),
        "first_instance": "counts 1441, 680, 67, 94; the 94 was acted on",
        "commit": "A293 sweep", "date": "2026-08-10",
        "found_by": "FOUND_BY_ADJUDICATION"},
    "UNCHECKED_IMPOSSIBILITY_CLAIM": {
        "definition": ("'cannot be tested' asserted about the test space "
                       "without the evidence any other assertion needs; "
                       "untested it is UNCHECKED, not IMPOSSIBLE"),
        "first_instance": "clause 2 declared undemonstrable, disproved by one file",
        "commit": "295d41a", "date": "2026-08-11",
        "found_by": "FOUND_BY_ADJUDICATION"},
    "METRIC_MUTATED_BY_ITS_OWN_OBSERVATION": {
        "definition": ("a counter incremented by the act of observing "
                       "the system it counts, so routine use of the "
                       "monitored thing destroys the signal"),
        "first_instance": "the A328 opt-out count, written by the test harness",
        "commit": "77c8d1c", "date": "2026-08-12",
        "found_by": "FOUND_BY_ADJUDICATION"},
    "OBSERVATION_WINDOW_NARROWER_THAN_EVENT": {
        "definition": ("the observation is read through a slice narrower "
                       "than the event, so part of the event never "
                       "enters the record and is unrecoverable"),
        "first_instance": ("two FAILED lines, one read; and the "
                           "extent-skip stderr echo, both through tail"),
        "commit": "7bb6563", "date": "2026-08-12",
        "found_by": "FOUND_BY_ADJUDICATION"},
    "TRANSCRIBED_PROSE_NUMBER_DIVERGING_FROM_COMPUTED_FIELD": {
        "definition": ("a number written into prose beside a computed "
                       "field, free to drift from it"),
        "first_instance": "prose/computed divergence in a measurement record",
        "commit": "pre-A190", "date": "2026-08-09",
        "found_by": "FOUND_BY_AUTHOR_REVIEW"},
    "UNENUMERATED_DIMENSION_NOT_CELL": {
        "definition": ("a dimension of the outcome space never "
                       "identified, so no cell for it is missing and "
                       "the omission is invisible to a cell census"),
        "first_instance": "A280",
        "commit": "A280", "date": "2026-08-10",
        "found_by": "FOUND_BY_ADJUDICATION"},
    "IDENTITY_KEY_SENSITIVE_TO_INVOCATION_CONTEXT": {
        "definition": ("a registered identity fails to match because "
                       "the producing tool emits it in a different form "
                       "than the register stores, so a correctly "
                       "registered item presents as unregistered and "
                       "the gate refuses for a reason true of the key "
                       "and false of the world"),
        "first_instance": "row-2 closure: pytest emitted a rootdir-relative prefix",
        "commit": "12e3759", "date": "2026-08-12",
        "found_by": "FOUND_BY_FIRING"},
    "REFUSAL_FROM_UNINTENDED_CAUSE": {
        "definition": ("a control refuses, the refusal is real, and its "
                       "cause is not the condition under test, so the "
                       "attempt is credited with a detection it did not "
                       "make"),
        "first_instance": "the zsh word-splitting class-2 hostile attempt",
        "commit": "12e3759", "date": "2026-08-12",
        "found_by": "FOUND_BY_FIRING"},
    "COVERAGE_FOLLOWS_EXECUTION_NOT_STAKES": {
        "definition": ("a protection surface that grows around what the "
                       "execution path happens to read, rather than "
                       "around what results depend on. Artifacts no "
                       "code reads are unprotected regardless of how "
                       "load-bearing they are, and the exposure is "
                       "invisible precisely because nothing touches "
                       "them"),
        "first_instance": ("docs/roadmap/palt_m6/ — 1636 record files, "
                           "none bound; the commit path reads none"),
        "second_instance": ("render_spend/firing_trace.jsonl — the "
                            "output of the A38 positive-control "
                            "instrument, the artifact that exists to "
                            "prove a firing was recorded, was itself "
                            "unrecorded by the binding (A409)"),
        "commit": "6eb8e58", "date": "2026-08-12",
        "found_by": "FOUND_BY_ADJUDICATION",
        "why_it_outranks_the_others": ("it names why the other thirteen "
                                       "were findable and this one was "
                                       "not: the others lived where "
                                       "something ran")},
    "DANGLING_AUTHORITY_REFERENCE": {
        "definition": ("a record cites a ruling, requirement or artifact "
                       "by identifier, and the identifier does not "
                       "resolve; the obligation survives downstream on "
                       "the strength of the citation alone"),
        "distinctness_proved_both_directions": {
            "caught_by_22_missed_by_13_and_21": ("a274 cites A275, which "
                                                 "does not exist; nothing "
                                                 "is captured or "
                                                 "overwritten and no "
                                                 "definition is shadowed"),
            "caught_by_13_and_21_missed_by_22": ("an overwritten capture "
                                                 "and a shadowed "
                                                 "__post_init__ involve "
                                                 "no citation at all")},
        "first_instance": "a274 -> A275; it propagated through four launchers",
        "commit": "a697796", "date": "2026-08-12",
        "found_by": "FOUND_BY_ADJUDICATION",
        "disposition_on_first_observation": "EXHIBITED"},
    "GUARD_SHADOWED_BY_A_LATER_DEFINITION": {
        "definition": ("a guard is written, is syntactically valid, and "
                       "never executes because a later definition in the "
                       "same scope replaces it"),
        "distinctness_proved_both_directions": {
            "caught_by_21_missed_by_13": ("a shadowed __post_init__ "
                                          "captures nothing and "
                                          "overwrites nothing; retention "
                                          "is irrelevant, the code never "
                                          "runs"),
            "caught_by_13_missed_by_21": (".tier2_gate_output overwritten "
                                          "each run — the capture code "
                                          "executes correctly and is "
                                          "shadowed by nothing")},
        "first_instance": "the 3w route guard, a second __post_init__ on ConfirmationAction",
        "second_occurrence_of_the_shape": "the A387 guard, which existed and was never called",
        "commit": "a3a7395", "date": "2026-08-12",
        "found_by": "FOUND_BY_FIRING",
        "disposition_on_first_observation": "EXHIBITED"},
    "MEASURE_CONFOUNDED_BY_A_PROCESS_VARIABLE": {
        "definition": ("a measure responds to how the record was "
                       "produced as well as to what it records, so a "
                       "change in process is indistinguishable from a "
                       "change in subject"),
        "distinctness_proved_both_directions": {
            "caught_by_twenty_missed_by_sixteen": (
                "undecomposed DOUBLED moves from {} to {margins: 2} when "
                "the baseline replay is switched on with NO change in "
                "what was decided — confounded; and it does respond to a "
                "real subject change, so it is not insensitive"),
            "caught_by_sixteen_missed_by_twenty": (
                "a size-only measure over a digest swap reads 25 -> 25 — "
                "insensitive; and no process variable enters it at all, "
                "so it is not confounded")},
        "second_instance_exhibited": (
     "A591 — the CROSS-SEED PAIR COMPARISON. Five of the seven "
     "REQUIRED_DISTINCTIONS vary family and seed together and no record "
     "separates them: POWDER_MATTE 40 vs POWDER_SATIN 41, POWDER_SATIN "
     "41 vs CREAM 48, PRESSED_POWDER 47 vs POWDER_MATTE 40, SHIMMER 130 "
     "vs POWDER_METALLIC 140, SHIMMER 63 vs GLITTER 61. The remaining "
     "two seed both members from one ensemble constant and are "
     "SAME_SEED. NOT an error and nothing is withdrawn: A591 rules a "
     "cross-seed comparison legitimate where the seed-induced variation "
     "is measured and declared small relative to the effect, and "
     "illegitimate only SILENTLY. On the census rig the section 7 "
     "seed-only control bounds POWDER_MATTE 80 vs 81 at relative effect "
     "0.0380 against a 0.25 bar; that bound is for THAT family at THOSE "
     "seeds and is expressly not carried to any pair's own members. "
     "found_by FOUND_BY_AUTHOR_REVIEW, distinct from this class's "
     "first-instance route. a600_cross_seed_scope.json."),
 "first_instance": "reconcile_decision_surface DOUBLED, mixing BASELINE_REPLAY with PANEL_ACTION",
        "commit": "6e9d2fe", "date": "2026-08-12",
        "found_by": "FOUND_BY_ADJUDICATION",
        "disposition_on_first_observation": "EXHIBITED"},
    "MULTIPLICITY_ERASED_BY_A_SET_COMPARISON": {
        "definition": ("a control compares populations as sets, so a "
                       "subject appearing N times and once are "
                       "indistinguishable to it"),
        "distinct_from_ten": ("ten is about which of several acts "
                              "governs; nineteen is about the control "
                              "being unable to see that several exist"),
        "detection": ("any check built on set difference reports a "
                      "multiplicity table alongside its difference, or "
                      "declares multiplicity out of extent"),
        "first_instance": "reconcile_decision_surface against shade_names x2 on version 2",
        "commit": "7a7cb16", "date": "2026-08-12",
        "found_by": "FOUND_BY_AUTHOR_REVIEW",
        "disposition_on_first_observation": "EXHIBITED"},
    "FIELD_NEITHER_SURFACED_NOR_DECLARED_WITHHELD": {
        "definition": ("a field exists in the subject, no surface "
                       "displays it, and no record states why it is not "
                       "displayed"),
        "distinct_from_seventeen": ("seventeen is decided-but-unshown; "
                                    "eighteen is present-but-neither-"
                                    "shown-nor-declared, and eighteen is "
                                    "undetectable by seventeen's check "
                                    "because the field appears in "
                                    "neither population it compares — "
                                    "DEMONSTRATED, not asserted"),
        "detection": "assert INTENT field set == SURFACED u DECLARED_WITHHELD",
        "first_instance": ("10 UNOFFERED fields on the ES3083 intent, "
                           "including regulatory_zones at 0.9 and "
                           "HARD_VISIBLE_CONSTRAINT"),
        "commit": "4d2c2c8", "date": "2026-08-12",
        "found_by": "FOUND_BY_ADJUDICATION",
        "disposition_on_first_observation": "EXHIBITED"},
    "DECISION_WITHOUT_A_REVIEW_SURFACE": {
        "definition": ("a record carries a decision attributed to an "
                       "actor, and no surface available to that actor "
                       "could have displayed it for inspection or "
                       "revision"),
        "detection": ("for every field_name in a saved confirmation "
                      "record, assert membership in the set of field "
                      "names the panel renders"),
        "first_instance": ("shade_names on task 9 — a baseline CONFIRM "
                           "with no panel row; the owner confirmed 16 "
                           "fields and the record attributed 17"),
        "commit": "da5ddc1", "date": "2026-08-12",
        "found_by": "FOUND_BY_AUTHOR_REVIEW",
        "disposition_on_first_observation": "EXHIBITED"},
    "MEASURE_INSENSITIVE_TO_ITS_SUBJECT": {
        "definition": ("a check reporting a property that does not vary "
                       "with the condition it is cited as evidence for: "
                       "it produces a correct value, every time, that "
                       "discriminates nothing"),
        "first_instance": ("the eight-block byte diff against a digest "
                           "replacement — EXTENT_DIGESTS read 242 -> 242 "
                           "whether or not the rebind happened"),
        "commit": "6687ac4", "date": "2026-08-12",
        "found_by": "FOUND_BY_AUTHOR_REVIEW",
        "cure": "report a property that varies with the condition, or add one"},
    "IDENTITY_COMPUTED_FROM_UNSYNCED_MANIFEST": {
        "definition": ("an identity hashed while a bound artifact's "
                       "on-disk state differs from the digest the "
                       "corpus stores, yielding an identity no tree can "
                       "reproduce — silent, permanent, and undetectable "
                       "after the fact"),
        "first_instance": "near-miss this arc, caught by recomputing after rebinding",
        "commit": "3d46b32", "date": "2026-08-12",
        "found_by": "FOUND_BY_FIRING"},
    "CAPTURE_WITHOUT_RETENTION": {
        "definition": ("output captured to a fixed path and overwritten "
                       "each run, satisfying the letter of "
                       "capture-then-display while leaving no series: "
                       "the current observation is available and the "
                       "history is destroyed as it is made"),
        "first_instance": ".tier2_gate_output, overwritten every run",
        "commit": "2ed4e50", "date": "2026-08-12",
        "found_by": "FOUND_BY_AUTHOR_REVIEW"},
    "PROVENANCE_ASSERTED_BUT_NOT_CONTENT_BOUND": {
        "definition": ("a provenance field that the CALLER supplies "
                       "rather than the CONTENT determines records the "
                       "caller's claim, not the subject. Omission is "
                       "closed; forgery is not."),
        "first_instance": (
            "A575 — family, seed and source_kind in the 22f7024 "
            "provenance instrument. The pixel digest is taken over the "
            "loaded frame and the sidecar's render/material identities "
            "come from the artifact, so those are content-bound; family "
            "and seed are passed in by the caller, and a synthetic "
            "array can be stamped source_kind SCENE_LINEAR_EXR by "
            "convention alone. 3aa closes the case where a number "
            "arrives with NO inputs named; it does not make a named "
            "input true. Promoted from the executor's own declared "
            "bound rather than filed as a finding — a real limit of a "
            "working instrument, recorded instead of papered over."),
        "commit": "22f7024", "date": "2026-08-12",
        "found_by": "FOUND_BY_AUTHOR_REVIEW"},
    "DETERMINED_IN_FACT_NOT_IN_LAW": {
        "definition": ("a term whose meaning is fixed only by an "
                       "artifact outside the identity chain, so a "
                       "result citing it cannot be shown to have cited "
                       "what it cited"),
        "first_instance": "the relative_effect denominator in a code comment",
        "third_instance_campaign_scale": (
            "A527 — four published cells (M_v_S/SHEEN 0.09112, "
            "P_v_M/SHEEN 0.11572, S_v_C/FWHM 0.0343, S_v_C/GRAN 0.1923) "
            "rest on per-seed values whose frame inputs no artifact "
            "records. The value 0.041395 appears in exactly one file in "
            "the corpus — the result that publishes it. Largest instance "
            "in the register; marked "
            "PUBLISHED_WITHOUT_RECOVERABLE_INPUTS, not withdrawn."),
        "second_instance_exhibited": ("A451 — apply_confirmations resolves "
                                      "accumulated acts by ITERATION ORDER; "
                                      "the rule was nowhere written and no "
                                      "test failed on reordering. Minted for "
                                      "this shape and sat unfired against "
                                      "this code. Named at 3v as "
                                      "LAST_WRITE_PER_ATTRIBUTE_WINS_EXCEPT_"
                                      "DELETE_WHICH_DOMINATES; behaviour "
                                      "unchanged."),
        "commit": "48f6bd4", "date": "2026-08-07",
        "found_by": "FOUND_BY_AUTHOR_REVIEW"},
    #: Both entries below are minted by OWNER RULING §BH5(a), which
    #: answered the conditional "or register the class if it does not
    #: exist" that commit P declined to answer unilaterally. Membership
    #: was tested BY NAME against this constant before the ruling, not
    #: recalled: neither name was present, against 23 entries.
    "UNIT_MISMATCH": {
        "definition": ("a counter that is internally honest in a unit "
                       "nobody declared, measured against a ceiling "
                       "denominated in a DIFFERENT unit. Every "
                       "individual increment is defensible. The sum is "
                       "meaningless. No arithmetic check can catch it, "
                       "because the arithmetic is correct; only naming "
                       "the unit catches it."),
        "first_instance": (
            "§BH4(b) / commit 04d5b44 — the spreads campaign spend "
            "counter. RENDERS declared a ceiling of 80 and the counter "
            "incremented per ensemble ITEM, so one increment of 6 meant "
            "twelve renders in a texture phase and twenty-two in the "
            "glitter phase. The recount measured 101 renders against "
            "that cap of 80 — 60 auditable from the records, 41 "
            "derivable only from scratch that git ignores. Not one "
            "increment was wrong."),
        "distinctness_proved_both_directions": (
            "against MEASURE_CONFOUNDED_BY_A_PROCESS_VARIABLE, the "
            "nearest neighbour. That class catches and this one misses: "
            "a DOUBLED replay, where a measure shifts with production "
            "process and no ceiling and no unit comparison exist at "
            "all. This catches and that one misses: a perfectly "
            "unconfounded 1:1 counter — as the lobe phase actually is — "
            "compared against a ceiling denominated in cost or in "
            "hours; the process class finds nothing there and the "
            "comparison is still invalid. Commit P declined to mint "
            "because that separating case was HYPOTHETICAL in this "
            "campaign. §BH5(a) ruled MINT and §BH5(f) closed the soft "
            "point on the owner's own wording, §BH4(b)'s 'bar' limb "
            "covering exactly the cost/hours case."),
        "disposition_on_first_observation": (
            "PUT TO THE OWNER, NOT MINTED. Commit P recorded the breach "
            "and filed the counter defect under "
            "MEASURE_CONFOUNDED_BY_A_PROCESS_VARIABLE rather than "
            "appending to this APPEND-ONLY register unilaterally. Its "
            "stated second reason was measured FALSE at §BH5(e) — it "
            "held that 'the register requires first_instance and "
            "second_instance fields', but a field census reads "
            "second_instance at 2/23 and this entry carries none. The "
            "judgment stands on its first reason; the factual claim "
            "does not, and both are recorded so the ruling is not read "
            "as overriding a fact when it overrode a judgment."),
        "commit": "04d5b44", "date": "2026-08-29",
        "found_by": "FOUND_BY_ADJUDICATION"},
    "TWO_ROOTS_MEASUREMENT": {
        "definition": ("a search whose ROOT or KEY SHAPE is wrong "
                       "returns a clean, confident, false NEGATIVE. A "
                       "wrong path errors and gets fixed; a narrow root "
                       "or a mis-shaped key exits 0 with nothing and "
                       "reads as evidence of absence. 'I found nothing' "
                       "is not a finding until the root and the shape "
                       "of the search are stated with it."),
        "first_instance": (
            "the repo has two roots — git root bbrose-systemOS, "
            "pytest/Django root bbrose_design_os beneath it — and docs/ "
            "and tools/ are tracked under BOTH, so a bare relative path "
            "is valid in both, exits 0, and returns different content "
            "with no error at all. Three SILENT modes were measured "
            "2026-08-22 and pinned by test_two_roots_collision_guard.py "
            "at commit aa84eb3, 10 tests each with a fired negative "
            "control: `git show HEAD:<path>` ignores the cwd; the "
            "docs//tools/ full-path collision; and `git status --short` "
            "on a path absent from this root, which warns to stderr and "
            "prints nothing at exit 0, reading as 'unmodified'."),
        "second_instance_exhibited": (
            "the class kept firing AFTER it was pinned, in costumes the "
            "pin does not cover. §AY1's narrow root. A WRONG KEY at "
            "commit P: four greps for class NUMBERS against a register "
            "keyed by NAME, each correctly executed, each returning a "
            "clean empty result that was read as evidence this register "
            "did not exist. §BH4(c) at commit Q: '21 sites across 9 "
            "files' is the pytest-root reading of a count that is 23 "
            "across 10 from the git root, the dropped file being "
            "OWNER_BLOCKER_CLEARANCE.md — the document carrying the "
            "ruling being executed. And once inside the §BH5(e) "
            "transcription that measured this class ABSENT, where a "
            "lowercase key pattern printed 0 entries against a register "
            "holding 23. A class firing during its own registration is "
            "evidence about the class."),
        "distinctness_proved_both_directions": (
            "against OBSERVATION_WINDOW_NARROWER_THAN_EVENT, the "
            "nearest neighbour, separating on real instances in both "
            "directions. That class catches and this misses: a window "
            "closing before an event completes, where the search shape "
            "is correct and only the interval is short. This catches "
            "and that misses: a whole-corpus search with no window at "
            "all, wrong only in its root or its key. The first is a "
            "defect of TRUNCATION; this is a defect of GENERALISATION — "
            "a result true of the subset, read as true of the whole."),
        "disposition_on_first_observation": (
            "PINNED BY A TEST BUT NEVER REGISTERED, which is the reason "
            "this entry exists. Measured at commit P: the name was used "
            "as authority across four files — progress_tracker.json "
            "(one narrative field inside a correction note about a "
            "different node), OWNER_BLOCKER_CLEARANCE.md, "
            "test_characterization_protocol.py (a comment, not an "
            "assertion) and this very file, ~540 lines from the "
            "constant it was absent from — while resolving to NO entry "
            "at all. That is DANGLING_AUTHORITY_REFERENCE in the "
            "strongest form yet found, and it also supersedes §BH4(k)(2), "
            "which reasoned from the tracker field as though it were a "
            "registration. Registered here by §BH5(a)."),
        "commit": "aa84eb3", "date": "2026-08-22",
        "found_by": "FOUND_BY_FIRING"},
}


#: A352 repair 3 / 3k — the suite manifest stays a large file, but its
#: DIGEST lives here, inside the identity. The gate verifies the digest
#: BEFORE reading the manifest, so the file can no longer be edited
#: without protocol_identity() moving. The defect this closes is that
#: the gate's own declared extent was DETERMINED_IN_FACT_NOT_IN_LAW.
EXTENT_DIGESTS = {
    #: rebound 2026-08-20 at WI-3J/§AR. The manifest declared 318 files
    #: against 362 collected and had done since 2026-08-12, so A327(a) —
    #: the clause that detects a test FILE disappearing — was blind to 44
    #: files holding 1,310 tests, 17.8% of the suite. Blind in the worst
    #: direction: deleting an undeclared file took the refusal count from
    #: 44 to 43, because the file stopped appearing in
    #: `actual_files - declared`. The instrument reported improvement when
    #: coverage was lost. Regeneration was purely additive, 44 added and 0
    #: removed, which is §AR4(1)'s precondition and was checked before
    #: anything was applied.
    #: The same amendment raises the TIER_1 floors, which regenerate_manifest
    #: used to carry forward verbatim: test_characterization_protocol.py
    #: went 28 -> 66 against its measured extent, inside the gate that
    #: exists because that exact file once went to zero bytes.
    #: rebound 2026-08-21 at §AV6. ONE test file was added —
    #: test_av5_artefact_withheld.py, the 11 tests that WATCH the three
    #: artefact closures fire — and A327(a) caught that it was outside the
    #: declared extent. The regeneration was purely additive, 1 added and 0
    #: removed, checked under §AR4(1) BEFORE anything was applied. Floors
    #: rose and none fell: total_floor 7,408 -> 7,422, tier1 unchanged.
    #: rebound 2026-08-21 at §AX. THREE test files were added and A327(a)
    #: caught every one of them: test_au3_brand_usage.py (19) and
    #: test_au3_divider_gates.py (24), both new in this tranche, plus
    #: test_aw_emitter_closure.py (8), which is §AW's and had been sitting
    #: UNTRACKED since that tranche — its ruling was committed and its tests
    #: were not, so the extent gate found a gap this executor had not noticed
    #: and would not have looked for. That is the clause earning its keep on
    #: a file nobody was thinking about. Regeneration purely additive, 3
    #: added and 0 removed, checked under §AR4(1) BEFORE anything was
    #: applied. Floors rose and none fell: total_floor 7,422 -> 7,475,
    #: tier1 unchanged. The +53 is 51 collected tests from the three files
    #: plus the 2 added to test_container_line_weight.py, which is already
    #: declared — so the total reconciles without a residue.
    #: rebound 2026-08-21 at §AY1. ONE file added,
    #: apps/pipeline/tests/test_ay1_outbound_guard.py — the 14 tests that
    #: WATCH the outbound-call guard refuse a real connection to a host this
    #: machine can genuinely reach. A327(a) caught it, as it has now caught
    #: every test file added in four consecutive tranches. Regeneration
    #: purely additive, 1 added and 0 removed, checked under §AR4(1) BEFORE
    #: anything was applied. Floors rose and none fell: total_floor
    #: 7,475 -> 7,489, tier1 unchanged. The +14 is exactly the guard file's
    #: collected count, so the total reconciles without a residue.
    #: REBOUND A SECOND TIME IN THE SAME TRANCHE, 8faa48a16268ffdf ->
    #: 52e0f544d91be347, AND THE DECLARED CONTENT DID NOT CHANGE BY ONE BYTE.
    #: `tier2_gate.py --regenerate-manifest` reported `added (0) / removed
    #: (0)` and still minted a new digest, because the manifest embeds a
    #: `generated` wall-clock stamp: 04:35:34.199453Z -> 08:16:36.851849Z was
    #: the ENTIRE diff besides it. THE GENERATOR IS NOT IDEMPOTENT. Running
    #: it defensively, on a manifest that was already correct, invalidated a
    #: correct chain and cost a rebind, an identity recompute and a re-pin —
    #: which is the treadmill three prior tranches climbed while calling it
    #: an ordering mistake (§AZ0(h)). The rule that follows from it: run the
    #: manifest generator ONLY when a test file was actually added or
    #: removed, never "to be safe", because for this record `--regenerate`
    #: is a WRITE and not a query. The stale timestamp was NOT edited back to
    #: fake idempotence; the append-only diff record and the REFUSED ledger
    #: line both stand as written (§AZ0(l)).
    #: rebound 2026-08-22 at the two-roots tranche, 52e0f544d91be347 ->
    #: 307ce4c380fa0f02. ONE file added,
    #: apps/pipeline/tests/test_two_roots_collision_guard.py — 10 tests that
    #: pin the git-root/Django-root path collision and demonstrate its three
    #: silent modes by execution. A327(a) caught it, as it has now caught
    #: every test file added in five consecutive tranches. Regeneration purely
    #: additive, 1 added and 0 removed, checked under §AR4(1) against a BYTE
    #: BACKUP rather than against the generator's own printout, BEFORE
    #: anything was applied.
    #: THIS REGENERATION WAS EARNED, unlike the one immediately above: a test
    #: file actually moved, which is the §AZ0(l) precondition. It also exposed
    #: something the previous entry could not: the TIER_1 floor for
    #: test_palette_statistics.py was 49 in BOTH copies while the file
    #: collected 50. dab25db added the 50th test and raised neither. The §AR2
    #: guard compares the two copies to each other, so two copies stale by the
    #: same amount are invisible to it — the recount from disk is the only
    #: thing that could have found this, and it sat wrong for two commits.
    #: Ground truth taken from `pytest --collect-only` (50 and 66), not from
    #: either declared copy; guarded_commit.sh raised to 50 in this amendment.
    #: rebound 2026-08-27 at §BC(h)/C10, 307ce4c380fa0f02 -> 65aef9fb1a3660cd.
    #: ONE file added, apps/ire/tests/test_c10_mark_width.py — 15 tests that
    #: measure the owner-ruled 0.55 mark share as an EMITTED millimetre width
    #: against MINIMUM_WIDTH_MM_PRINT. A327(a) caught it outside the declared
    #: extent, as it has now caught every test file added in SIX consecutive
    #: tranches. Six for six is no longer a run of luck and is worth naming as
    #: the measured base rate: this executor does not remember the manifest,
    #: and the guard is the only reason that has never once cost coverage.
    #: Regeneration purely additive, 1 added and 0 removed, checked under
    #: §AR4(1) against a BYTE BACKUP (/tmp backup sha256 equal to the tracked
    #: file before applying) rather than against the generator's own printout.
    #: EARNED under §AZ0(l): a test file actually moved.
    #: THE RECOUNT CLOSED A PREDICTION RATHER THAN FINDING A NEW DEFECT, and
    #: the distinction matters because the last entry's recount DID find one.
    #: tier1 test_palette_statistics.py 50 -> 51 here. That is not drift
    #: discovered now: `4cda10f` added the test and raised the guarded_commit
    #: .sh copy at the time, and the comment at guarded_commit.sh:85 recorded
    #: in writing that "the MANIFEST copy still says 50 and will until the
    #: next regeneration". This is that regeneration. The two copies agree at
    #: 51 for the first time since 4cda10f, and the §AR2 assertion never
    #: fired throughout — correctly, because it is one-directional and
    #: shell-above-manifest is the safe direction.
    #: total_floor 7,567 -> 7,643, and a floor bars FUTURE runs only.
    #: The +76 DOES NOT RECONCILE TO THE ADDED FILE AND IS NOT CLAIMED TO:
    #: the new file collects 15, measured with --collect-only. The other 61
    #: were already being collected and were sitting above a floor stale
    #: since 2026-08-22 — `total_floor` is `max(old, sum(collected))`,
    #: re-measured every regeneration under AR3(d), so it catches up in one
    #: step for every test added since the last legitimate trigger. Writing
    #: "76 tests added by this tranche" would have been a subtraction
    #: reported as a count, which is the §AV6 habit its own entry apologises
    #: for two paragraphs up.
    #: Day14: four new test files; actual collection and unchanged monotonic floors.
    #: 2026-10-29 (the owner's message, "Re-pin the four checks per PLAN.md"): the 42 test files the consolidation
    #: and the retirement moved to archive/ leave the declared list (diff-log entry 2026-10-28T20:47:11.922378Z, his
    #: third approved removal); nothing added; floors carried by the tool, never lowered.
    "suite_file_manifest": "f6753604cf1bcafa",
    #: A375 — the record manifest's own digest, or the problem has only
    #: moved: a large mutable artifact is bound by a digest, and the
    #: digest is bound by the corpus. Same terminating move as repair 3.
    #: rebound 2026-08-17 by the §R4/§S1 fallback-class registration, which
    #: writes two records under the declared root (gate_baseline.json gains
    #: its registrations block; fallback_class_defects.json is new). A375
    #: makes this drift EXPECTED — a node that writes records moves this
    #: digest and protocol_identity with no law edited — and the recipe
    #: below requires the update in the SAME amendment as the regeneration.
    #: rebound 2026-08-20 at WI-3G/§AJ. The regeneration recorded
    #: `+1 -0 ~2`: `suite_records/INDEX.json` was RECORD_UNDECLARED —
    #: committed into the bound root at d4f93e0 and again at 5d06ae6, both
    #: mine, with the manifest last regenerated at 8faccb7, before either.
    #: The two `~` are `flake_register.json` and `record_gate_ledger.jsonl`,
    #: both APPEND_ONLY and both legitimately grown, which is why check()
    #: refused on one row and not three.
    #: rebound 2026-08-20 at WI-3J/§AR alongside the entry above. The
    #: regeneration recorded `+0 -0 ~3`: suite_file_manifest.json,
    #: suite_manifest_diffs.json and record_gate_ledger.jsonl. Nothing
    #: added, nothing removed — the extent repair rewrote records that
    #: were already declared, which is the shape A375 calls EXPECTED.
    #: rebound 2026-08-21 at §AV5, LATE — and the lateness is the entry.
    #: §AV3 regenerated the manifest (`+0 -0 ~3`: suite_file_manifest.json,
    #: suite_manifest_diffs.json, record_gate_ledger.jsonl — the same
    #: `~`-only shape as §AR above) and committed WITHOUT rebinding, which
    #: is precisely what the recipe below forbids in the words "in the same
    #: amendment, never separately". It left `SplitIdentityTests` red for a
    #: full tranche.
    #: WHY IT WAS NOT NOTICED, which is the part worth keeping: §AV3 ran
    #: `record_integrity.py`, read `RECORD_INTEGRITY=OK records=1734
    #: failing=0`, and reported that as evidence the regeneration was
    #: complete. That tool checks the LEDGER. It does not read
    #: EXTENT_DIGESTS and cannot answer whether the pin still matches, so
    #: the OK was true and irrelevant — an instrument's verdict borrowed
    #: for a question it was not asked. A387 exists because this class of
    #: error is silent; here it was loud, and still took a tranche.
    #: rebound 2026-08-21 at §AX. Regeneration recorded `+0 -0 ~3` again:
    #: record_gate_ledger.jsonl, suite_file_manifest.json,
    #: suite_manifest_diffs.json — the same `~`-only shape as §AR and §AV5.
    #: THE ORDER IS STEP ONE FOR A REASON AND I STARTED AT STEP TWO. A391
    #: reads "records, regenerate, rebind, compute, pin". This tranche ran
    #: regenerate/rebind/compute/pin over `suite_file_manifest` first, pinned
    #: protocol_identity to a046c26c242831a3, and only then discovered
    #: `record_integrity.py` refusing on a RECORD_DIGEST_MISMATCH — the
    #: RECORDS step, unrun. Clearing it moved record_digest_manifest.json
    #: from b924d02e… to a32b4daa…, which invalidated the identity pinned
    #: minutes earlier and forced the whole chain a second time.
    #: The distinction from §AV5 is worth keeping because it is the entire
    #: value of A387: §AV5's omission was SILENT and cost a full tranche;
    #: this one was LOUD and cost one re-run. Same defect class, two orders
    #: of magnitude apart in cost, and the difference is that the guard was
    #: allowed to speak before the commit rather than after it. §AV5's entry
    #: says the OK was "true and irrelevant"; mine is that the chain was
    #: complete and misordered, which the recipe below does not yet forbid
    #: in words. It says "never separately". It does not say "never out of
    #: order", and out of order is what happened.
    #: rebound 2026-08-21 at §AY1. `+0 -0 ~3` a fourth time —
    #: record_gate_ledger.jsonl, suite_file_manifest.json,
    #: suite_manifest_diffs.json — the same shape as §AR, §AV5 and §AX.
    #: THE ORDER IS RIGHT AND IT IS NOT ENOUGH, WHICH IS A DIFFERENT DEFECT
    #: FROM §AX'S. This tranche ran A391 step 1 exactly as written and read
    #: `RECORD_INTEGRITY=OK records=1734 failing=0`. Step 2 then regenerated
    #: the suite manifest — and STEP 2 IS ITSELF A RECORD WRITE. It moved
    #: three declared records, so step 1's OK was invalidated by the very
    #: next step of the recipe that ordered it. Running record_integrity.py
    #: again before rebinding returned RECORD_DIGEST_MISMATCH on
    #: suite_file_manifest.json, 3b2de42e… -> 8faa48a1…: the chain followed
    #: in the prescribed order, refusing anyway.
    #: §AX's entry read the failure as "complete and misordered". That was
    #: half of it. The other half is that a linear five-step recipe cannot
    #: describe a chain whose second step dirties its first, and no ordering
    #: of five distinct steps fixes that — the records step has to run
    #: TWICE. The recipe below now says so, and it says so because the chain
    #: was run rather than reasoned about (§AA). Had the second records pass
    #: been skipped, the rebind would have pinned a record_digest_manifest
    #: digest that record_integrity.py was already refusing, and
    #: guarded_commit.sh would have caught it at the records gate — loud,
    #: like §AX, not silent, like §AV5.
    #: AND THEN IT HAPPENED A THIRD TIME, FOR A NEW REASON, WHICH IS WHY THE
    #: SECOND PASS IS A RULE AND NOT A RITUAL. 6300c0500768f446 ->
    #: 53a6806e4aa96814. The §AS2(2) node move wrote progress_tracker.json;
    #: a defensive `--regenerate-manifest` then rewrote suite_file_manifest
    #: .json with nothing but a new timestamp (see above), which moved that
    #: record, the append-only diff record AND the ledger — `+0 -0 ~3` — so
    #: the records pass had to be re-earned once more before this rebind.
    #: MEASURED WHILE DOING IT, AND IT IS THE LARGER FINDING: the node move
    #: produced NO record diff at all. RECORD_ROOTS declares
    #: ("docs/roadmap",) and every refusal message quotes it, but PATTERNS
    #: binds docs/roadmap/palt_m6/**. Inside the DECLARED root there are
    #: 1,947 json/jsonl; 1,735 are bound; 212 ARE NOT CHECKED BY ANYTHING —
    #: among them progress_tracker.json, which carries all 106 nodes and is
    #: the file an owner reads to learn what is done, master_roadmap_v3.json,
    #: and acceptance/product_container_acceptance_rejection.json. The
    #: complement check that exists to catch a RECORD_KIND outside the
    #: binding pattern walks docs/roadmap/palt_m6 too, so it is structurally
    #: unable to see them. `records=1734 failing=0` is true and reads as
    #: coverage of the declared root, which it is not (§AY0(d)). NOT FIXED
    #: HERE: widening the pattern admits 212 records at once and would mint
    #: refusals across all of them inside a tranche about something else
    #: (§AC). Reported at §AZ0(m) and carried as an ask, not a fix.
    #: rebound 2026-08-22 at the two-roots tranche, 53a6806e4aa96814 ->
    #: 4afa98f85203874d, in the SAME amendment as suite_file_manifest above,
    #: which is what the recipe requires. `record_integrity.py --regenerate`
    #: reported `+0 -0 ~3` — the three records this tranche touched: the file
    #: manifest, the append-only diff log, and the ledger.
    #: A387 earned its keep here rather than merely existing: the three
    #: identity tests failed with UnsyncedManifest BEFORE computing anything,
    #: naming both digests and the A391 order. That is the whole point of
    #: asserting sync before hashing — the alternative failure is an identity
    #: no tree can reproduce, and it is silent.
    #: rebound 2026-08-27 at §BC(h)/C10, 4afa98f85203874d -> 413e1e2cb99d664c,
    #: in the SAME amendment as suite_file_manifest above, which is what the
    #: recipe requires. `record_integrity.py --regenerate` reported `+0 -0 ~3`
    #: — the file manifest, the append-only diff log, and the ledger: the same
    #: `~`-only shape as §AR, §AV5, §AX, §AY1 and the two-roots tranche.
    #: THE TWO-PASS RULE WAS FOLLOWED AND THE SECOND PASS WAS NOT A RITUAL.
    #: Step 1 returned `records=1734 failing=0` BEFORE the regeneration; step 2
    #: then wrote three declared records, invalidating that OK exactly as §AY1
    #: predicted it would; step 3 re-earned it. The value of the rule is that
    #: this is now boring — the entry above had to discover it by refusing.
    #: RE-BOUND 2026-08-29 at §BH4(b), commit P:
    #: dfa03eea8235bb33 -> a74fed4fcbc4de50, NET, one commit.
    #: It took FOUR passes to get there and the three discarded
    #: destinations are named in order below — 5a963b348ab26142,
    #: b269f918c546fc55, 7bf32c2efcec96ec — because each was bound,
    #: believed, and invalidated by the next thing this executor did, and
    #: the reasons all differ. None was ever committed. Read the header
    #: for what shipped and the narrative for what it cost.
    #: THE FOURTH PASS IS THE ONE WORTH THE WORDS. Passes two and three
    #: were process errors — a non-idempotent tool, then a false claim
    #: caught by the chain. The fourth was caught with the GATE ALREADY
    #: RUNNING GREEN, while reading ahead to the next commit: the record
    #: listed TWO_ROOTS_MEASUREMENT among classes it had "checked against
    #: the real register", and TWO_ROOTS_MEASUREMENT IS NOT IN THIS
    #: REGISTER. It is named in a comment in THIS FILE, ~540 lines below
    #: the constant it is absent from. The run was stopped and the record
    #: corrected; the finding is recorded there as a register-completeness
    #: measurement, and it supersedes §BH4(k)(2), which reasoned from a
    #: tracker field that is a citation and not a registration.
    #: WHAT MOVED IT IS THE §BH2 CASE FROM THE OTHER SIDE. There the
    #: propagation started with one thirteen-day-stale field inside an
    #: existing record; here it starts with a file that did not exist —
    #: `--regenerate` reported `+1 -0 ~1`, the `+` being
    #: spreads_ceiling_breach.json and the `~` the gate ledger. An ADDED
    #: record and an EDITED one are indistinguishable by the time they
    #: reach this constant, which is the same fact §BH2 recorded about
    #: honest corrections and silent re-scopings: every hash here covers
    #: the whole artifact below it and none of them can say WHY it moved.
    #: The chain is run to five this time precisely because §BH2 stopped
    #: at two, held a green from an instrument that cannot see this pin,
    #: and was refused by the gate. The note sits one line above the
    #: constant it is about, which is the only place it will be read.
    #:
    #: `--regenerate` IS NOT IDEMPOTENT, AND VERIFYING BY RE-RUNNING IT
    #: BREAKS THE THING YOU JUST BOUND. It appends one entry to the
    #: manifest's own `diffs` list on EVERY invocation (regenerate() in
    #: tools/record_integrity.py), so the file's bytes move even when the
    #: reported diff is `+0 -0 ~0`. This executor bound
    #: 5a963b348ab26142, re-ran `--regenerate` as a check, and watched a
    #: `+0 -0 ~0` line print while the digest went to b269f918c546fc55 —
    #: the binding was stale the instant it was confirmed. THE SECOND
    #: PASS THE RECIPE ASKS FOR MUST BE `--check`, WHICH DOES NOT WRITE.
    #: Note the shape: the diff line said nothing changed and it was
    #: telling the truth about RECORDS while being useless about BYTES.
    #: `diffs` now holds 70 entries, one per historical regeneration.
    #: rebound 2026-08-29 at §BH4(b), commit P — b269f918c546fc55 ->
    #: 7bf32c2efcec96ec. `+0 -0 ~2`: spreads_ceiling_breach.json (the
    #: breach record, REWRITTEN after this executor discovered mid-chain
    #: that the draft on disk asserted "THERE IS NO MASTER REGISTER OF THE
    #: NUMBERED CLASSES" about the very constant this file declares three
    #: hundred lines above — DEFECT_CLASS_REGISTER, 23 entries, bound into
    #: protocol_identity() — and cited two classes wrongly from memory)
    #: and record_gate_ledger.jsonl (commit O's gate run).
    #: THE CHAIN IS WHAT CAUGHT THE FALSE CLAIM, WHICH IS THE REASON TO
    #: WRITE IT DOWN HERE. The COMPUTE step reads protocol_identity()'s
    #: payload; `defect_class_register` is one of its nine keys; reading
    #: that payload is what made the register visible after four greps had
    #: each returned a clean, confident, empty result. They were searching
    #: for class NUMBERS and the register is keyed by NAME.
    #: THAT IS TWO_ROOTS_MEASUREMENT IN A THIRD COSTUME. Not a wrong path,
    #: which errors. Not a narrow root, which was §AY1's. A WRONG KEY —
    #: which returns exit 0 and nothing, and reads as evidence of absence.
    #: The record now cites every class BY NAME and mints none: see
    #: spreads_ceiling_breach.json, which puts UNIT_MISMATCH to the owner
    #: rather than appending it to this APPEND-ONLY register unilaterally.
    #: RE-BOUND 2026-08-29 at §BH4(c), commit Q:
    #: a74fed4fcbc4de50 -> 1e4e82003c328302. ONE pass, one `--regenerate`,
    #: `diffs` 72 -> 73. `+0 -0 ~2`: spreads_campaign_declaration.json (spend
    #: closed) and record_gate_ledger.jsonl. Counts did NOT move — 1735,
    #: append_only 6, revisable 1729 — and that is the visible difference
    #: from commit P one entry above, which ADDED a record and moved the
    #: total. This digest moved anyway. An added record and a ten-line status
    #: edit are the same event by the time they reach this constant.
    #: THE FOURTH FIRING OF TWO_ROOTS_MEASUREMENT WAS CAUGHT BEFORE THE
    #: WRITE, WHICH IS THE ONLY REASON IT IS A NOTE AND NOT A CORRECTION.
    #: Commit P shipped two false claims about DEFECT_CLASS_REGISTER because
    #: its NUMBERS were computed and its PROSE was recalled, and it closed
    #: that asymmetry for register claims only. Commit Q's writer still
    #: carried recalled prose of a different kind: "c1434e1efdb98a62 at 21
    #: sites across 9 files". Measured from the git root it is 23 sites
    #: across 10. The missing file is OWNER_BLOCKER_CLEARANCE.md — the
    #: document carrying the owner's ruling — which is tracked at the git
    #: root and invisible from the pytest root. Both greps exit 0. The
    #: writer now runs the census itself, from a PINNED root, and cannot
    #: emit the record if the count changes. Third costume was a wrong key;
    #: this is the narrow root again, §AY1's, unlearned in four days.
    #: rebound 2026-08-29 at §BH7/commit U, 1e4e82003c328302 ->
    #: ff18cb2d74866a94. Cause: P1's first act (§BH3, ruled to reading A by
    #: §BH7(a)) writes three new bound records under docs/roadmap/palt_m6 —
    #: `record_integrity.py --regenerate` reported `+3 -0 ~1`, the three new
    #: p1_audit records plus the ledger. THE SUITE MANIFEST WAS NOT
    #: REGENERATED and this is measured, not assumed: the recipe says
    #: regenerate ONLY when a test file was actually added or removed, and
    #: commit U adds and removes none. Because that regeneration is the
    #: stated CAUSE of the "run the records step TWICE" clause (§AY1), the
    #: clause does not apply and the records step ran ONCE. Two further
    #: measurements made the single pass safe rather than merely convenient:
    #: `.py` is NOT_A_RECORD ("source"), so P1's committed runner is unbound
    #: and costs no entry; and record_digest_manifest.json does not track
    #: ITSELF, so regenerating it cannot invalidate itself and no second
    #: pass is owed on that account either. The `~1` is the gate ledger,
    #: moved by the REFUSED check that measured the three records as
    #: RECORD_UNDECLARED before they were declared — that refusal is left in
    #: the ledger because it is an honest reading of the state at the time.
    #: Day14: four new test files; actual collection and unchanged monotonic floors.
    #: 2026-10-29 (the same re-pin): records regenerated after the fallback register, the allowlist, the declared
    #: list and its diff log changed (+0 −0 ~5); the value equals its zero-write preview.
    "record_digest_manifest": "b42bac83882054cf",
    "recipe": ("sha256 of the manifest file's bytes, first 16 hex; "
               "regenerate the manifest, then update this digest in the "
               "same amendment, never separately — and run A391's five "
               "steps IN ORDER: records first, because clearing a record "
               "refusal moves this very digest and silently invalidates "
               "any identity pinned before it (§AX). RUN THE RECORDS STEP "
               "TWICE: regenerating the suite manifest is itself a write "
               "to three declared records, so step 1's OK does not survive "
               "step 2 and must be re-earned before the rebind (§AY1). "
               "REGENERATE THE SUITE MANIFEST ONLY WHEN A TEST FILE WAS "
               "ACTUALLY ADDED OR REMOVED. It is a WRITE, not a query: it "
               "stamps `generated` with the wall clock, so a run that "
               "reports `added (0) / removed (0)` still mints a new digest "
               "and still costs a rebind, an identity recompute and a "
               "re-pin. Check `git status` first; if the manifest is clean "
               "and no test file moved, DO NOT RUN IT (§AY1/§AZ0(l))"),
}


#: The §16 canonical pairs the protocol MUST distinguish, with the rig
#: chosen by the physical question the pair raises. A protocol that
#: passes every pair except one has not finished M6.
REQUIRED_DISTINCTIONS = (
    (POWDER_MATTE, POWDER_SATIN, "DIFFUSE_MICROTEXTURE_RIG"),
    (POWDER_SATIN, CREAM, "DIFFUSE_MICROTEXTURE_RIG"),
    (PRESSED_POWDER, POWDER_MATTE, "DIFFUSE_MICROTEXTURE_RIG"),
    (SHIMMER, POWDER_METALLIC, "FLAKE_REFLECTION_RIG"),
    (SHIMMER, GLITTER, "GLITTER_PARTICLE_RIG"),
    (BAKED, PRESSED_POWDER, "BAKED_GEOMETRY_RIG"),
    (MARBLED, POWDER_MATTE, "MARBLING_STRUCTURE_RIG"),
)

#: Colour authority, restated because M6 touches shade fields: ES3083's
#: pan shades have NO authoritative colour source. Families are proven
#: on NEUTRAL placeholder shades; nothing here fabricates an RGB, Lab or
#: CMYK value for any Pantone token, and FB3090 remains UNSOURCED.
COLOUR_AUTHORITY = {
    "pan_shades": "ES3083_OWNER_CHOSEN_DESIGN_INTENT_NOT_MEASURED",
    "pan_shades_record": "docs/roadmap/palt_m6/es3083_shade_authority.json",
    "pan_shades_scope": "ES3083 only; FB3090 and FB3093 unchanged",
    "pantone_tokens": "SYMBOLIC_NAMED_REFERENCE_NO_VALUE_FABRICATED",
    "FB3090": "UNSOURCED",
}


class UnsyncedManifest(RuntimeError):
    """A387/3r — the identity may not be computed over a stale binding."""


def _assert_record_manifest_synced():
    """A387 — one assertion, before any identity is computed.

    IDENTITY_COMPUTED_FROM_UNSYNCED_MANIFEST: hashing while a bound
    artifact's on-disk state differs from the digest the corpus stores
    yields an identity no tree can reproduce. Silent, permanent, and
    undetectable after the fact. Near-missed this arc and caught only
    by recomputing after rebinding.
    """
    import hashlib
    import os
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))),
        "docs/roadmap/palt_m6/record_digest_manifest.json")
    if not os.path.exists(path):
        return
    on_disk = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    stored = EXTENT_DIGESTS["record_digest_manifest"]
    if on_disk != stored:
        raise UnsyncedManifest(
            f"record manifest on disk is {on_disk}, corpus stores "
            f"{stored} — regenerate and rebind BEFORE computing the "
            "identity (A391 order: records, regenerate, rebind, compute, pin)")


def protocol_identity() -> str:
    _assert_record_manifest_synced()
    payload = json.dumps({
        "schema": SCHEMA, "version": VERSION,
        "families": FAMILY_STRUCTURE, "sub_rigs": SUB_RIGS,
        "pass_law": PASS_LAW,
        "denominator_convention": DENOMINATOR_CONVENTION,
        "defect_class_register": DEFECT_CLASS_REGISTER,
        "extent_digests": EXTENT_DIGESTS,
        "independence_law": INDEPENDENCE_LAW,
        "required_distinctions": REQUIRED_DISTINCTIONS,
    }, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def protocol_status() -> dict:
    """Honest machine-readable status.

    Declared 2026-08-07; the last four declared realizations landed
    2026-08-14 (M6-PRODUCTS-OBSERVABILITY-TRACE-BOARDS,
    docs/roadmap/palt_m6/products/). REALIZED means the declared
    realizations exist — it does NOT mean complete: the 21-condition
    exit gate has not run, owner approval is not granted, and
    manufacturing authority is not established.
    """
    _assert_record_manifest_synced()
    return {
        "record_type": SCHEMA,
        "protocol_identity": protocol_identity(),
        "DECLARED": True,
        "REALIZED": True,
        "not_yet_implemented": [],
        "realized_last_2026_08_14": [
            "ES3083 twelve-pan multi-shade application",
            "FB3093 pressed-powder application (HONEST CEILING — pan "
            "dimensions unsourced; application on the product rect pan)",
            "product observability on real pan geometry (3 PASS / 2 "
            "product-level FAIL / 2 NOT_EXERCISED — recorded either way)",
            "workflow trace with production identifiers (task + 12 "
            "artifacts + queue control)",
        ],
        "still_gating": [
            "21-condition M6 exit gate (not run)",
            "owner approval (not granted)",
            "manufacturing authority (not established)",
        ],
        "colour_authority": COLOUR_AUTHORITY,
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }
