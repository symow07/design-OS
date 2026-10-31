"""PALT-M4C §I/§J — deterministic concept-to-contract mapping.

Closes the gap the §D audit found: ``build_palt_p1`` had no channel for
design information, so every dimension came from a generic default. Here
a ``PaletteDesignIntent`` is mapped onto the existing contract inputs,
and every resolved value records where it came from.

The rule the audit demands (§I): concept-derived information is used when
available. A generic default may be used ONLY when the concept does not
specify the feature, or the value is unresolved — and it must be labelled
as a default and must never override owner-confirmed information.

§J: a design requirement that collides with an engineering constraint is
neither silently discarded nor silently allowed to weaken the engineering
rule. It is reported as a ``PaletteDesignEngineeringConflict`` with
alternatives, and the owner decides.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from apps.pipeline.services import palette_design_intent as di

SCHEMA = "palette_intent_mapping/1.0"

FROM_INTENT = "CONCEPT_DERIVED"
FROM_DEFAULT = "GENERIC_DEFAULT"
FROM_OWNER = "OWNER_CONFIRMED"

SEVERITY = ("BLOCKING", "MAJOR", "MINOR", "ADVISORY")


@dataclass
class ResolvedValue:
    """One contract input, with its full provenance chain."""

    target: str                    # contract field it feeds
    value: object
    origin: str                    # FROM_INTENT / FROM_DEFAULT / FROM_OWNER
    source_field: str = ""
    source_reference: str = ""
    mapping_rule: str = ""
    scaling_rule: str = ""
    confidence: float = 0.0
    authority: str = "DESIGN_DEFAULT_NOT_MANUFACTURER_CONFIRMED"
    confirmation_state: str = di.PENDING
    conflict: str = ""

    def as_dict(self):
        return {
            "target": self.target, "value": self.value,
            "origin": self.origin, "source_field": self.source_field,
            "source_reference": self.source_reference,
            "mapping_rule": self.mapping_rule,
            "scaling_rule": self.scaling_rule,
            "confidence": round(float(self.confidence), 4),
            "authority": self.authority,
            "confirmation_state": self.confirmation_state,
            "conflict": self.conflict,
        }


@dataclass
class PaletteDesignEngineeringConflict:
    """§J — a design requirement that cannot coexist with engineering."""

    design_requirement: str
    engineering_conflict: str
    affected_components: list
    severity: str
    proposed_alternatives: list
    visual_impact: str
    dimensional_impact: str
    manufacturing_uncertainty: str
    recommended_resolution: str
    owner_decision_state: str = "PENDING_OWNER_DECISION"

    def as_dict(self):
        d = dict(self.__dict__)
        d["record_type"] = "palette_design_engineering_conflict/1.0"
        return d


# --- mapping rules ---------------------------------------------------------
# Each rule turns one intent field into one contract input. Rules are
# deterministic and declared; nothing is inferred at call time.
MAPPING_RULES = {
    "pan_count": {
        "target": "layout.pan_count",
        "rule": "a HARD counted pan_count sets the pan count exactly",
        "levels": (di.HARD,),
    },
    "rows": {"target": "layout.rows", "rule": "counted rows set rows",
             "levels": (di.HARD,)},
    "columns": {"target": "layout.columns",
                "rule": "counted columns set columns", "levels": (di.HARD,)},
    "pan_shapes": {"target": "pan.shape",
                   "rule": "a visibly circular pan sets shape=CIRCLE",
                   "levels": (di.HARD,)},
    "mirror_presence": {"target": "mirror.present",
                        "rule": "a visible mirror sets present=True",
                        "levels": (di.HARD,)},
    "hinge_location": {"target": "hinge.edge",
                       "rule": "a visible hinge edge sets the hinge edge",
                       "levels": (di.HARD,)},
    "clasp_location": {"target": "clasp.edge",
                       "rule": "a visible clasp edge sets the clasp edge",
                       "levels": (di.HARD,)},
    "opening_direction": {"target": "case.opening_direction",
                          "rule": "visible opening sets the direction",
                          "levels": (di.HARD,)},
    "width_height_relationship": {
        "target": "case.aspect_ratio",
        "rule": "a SOFT aspect impression sets a TARGET ratio, never a "
                "tolerance; the engineering envelope still governs",
        "levels": (di.SOFT,)},
    "margins": {"target": "layout.outer_margin_mm",
                "rule": "a SOFT margin impression scales the default margin "
                        "within the feasible range; never below the "
                        "engineering minimum",
                "levels": (di.SOFT,)},
    "spacing_rhythm": {"target": "layout.inter_pan_gap_mm",
                       "rule": "a SOFT spacing impression scales the gap "
                               "within the feasible range",
                       "levels": (di.SOFT,)},
    "corner_radius_impression": {
        "target": "case.corner_radius_mm",
        "rule": "a SOFT corner impression scales the corner radius",
        "levels": (di.SOFT,)},
    "mirror_proportion": {"target": "mirror.coverage_fraction",
                          "rule": "a SOFT mirror coverage impression scales "
                                  "the mirror within the lid",
                          "levels": (di.SOFT,)},
    "perceived_thickness": {"target": "case.outer_height_mm",
                            "rule": "a SOFT thickness impression scales the "
                                    "case height within the stack-up range",
                            "levels": (di.SOFT,)},
    "apparent_material": {"target": "material.primary",
                          "rule": "apparent material sets the render "
                                  "material only, never the geometry",
                          "levels": (di.SOFT, di.DECORATIVE)},
    "powder_finish_intent": {"target": "material.powder_finish",
                             "rule": "sets the powder finish family",
                             "levels": (di.SOFT, di.DECORATIVE)},
    "logo_position": {"target": "artwork.logo_zone",
                      "rule": "sets the logo zone",
                      "levels": (di.HARD, di.SOFT)},
    "typography_zones": {"target": "artwork.type_zones",
                         "rule": "sets typography zones",
                         "levels": (di.HARD, di.SOFT)},
}

SOFT_SCALES = {
    "generous": 1.25, "wide": 1.25, "large": 1.25,
    "balanced": 1.0, "even": 1.0, "regular": 1.0,
    "tight": 0.8, "narrow": 0.8, "minimal": 0.8, "slim": 0.8, "thin": 0.85,
    "soft": 1.2, "rounded": 1.2, "sharp": 0.5, "square": 0.4,
}


def _scale_for(value):
    """Deterministic scale for a SOFT impression. Unknown words scale 1.0
    and are recorded as unresolved rather than guessed."""
    text = str(value).strip().lower()
    for word, factor in SOFT_SCALES.items():
        if word in text:
            return factor, f"SOFT_SCALE[{word}]={factor}"
    return 1.0, "SOFT_SCALE_UNRESOLVED=1.0"


def map_intent(intent, defaults) -> dict:
    """Resolve every contract input from intent where possible.

    ``defaults`` is the generic contract dict the engine would have used
    on its own — exactly what the §D audit found it always uses.
    """
    resolved = {}
    conflicts = []
    used_fields = []

    for target, value in defaults.items():
        resolved[target] = ResolvedValue(
            target=target, value=value, origin=FROM_DEFAULT,
            mapping_rule="no concept field specifies this feature",
            authority="DESIGN_DEFAULT_NOT_MANUFACTURER_CONFIRMED")

    for f in intent.fields:
        if f.confirmation_state == di.REMOVED:
            continue
        rule = MAPPING_RULES.get(f.name)
        if rule is None:
            continue
        if f.constraint_level not in rule["levels"]:
            conflicts.append(PaletteDesignEngineeringConflict(
                design_requirement=f"{f.name} = {f.value!r}",
                engineering_conflict=(
                    f"{f.name} was extracted as {f.constraint_level} but "
                    f"its mapping rule only accepts "
                    f"{', '.join(rule['levels'])}"),
                affected_components=[rule["target"]],
                severity="MINOR",
                proposed_alternatives=[
                    "re-extract the field at the accepted level",
                    "leave the generic default in place"],
                visual_impact="the concept's expression of this feature is "
                              "not carried into the model",
                dimensional_impact="none — the default stands",
                manufacturing_uncertainty="none",
                recommended_resolution="owner reclassifies the field").
                as_dict())
            continue

        target = rule["target"]
        origin = FROM_OWNER if f.is_design_authority else FROM_INTENT
        if f.constraint_level == di.HARD:
            value, scaling = f.value, "EXACT (hard visible constraint)"
        elif f.constraint_level == di.SOFT:
            base = defaults.get(target)
            factor, scaling = _scale_for(f.value)
            value = (round(base * factor, 4)
                     if isinstance(base, (int, float)) else f.value)
        else:
            value, scaling = f.value, "DECORATIVE — expression only"

        resolved[target] = ResolvedValue(
            target=target, value=value, origin=origin,
            source_field=f.name, source_reference=f.source_reference,
            mapping_rule=rule["rule"], scaling_rule=scaling,
            confidence=f.confidence,
            authority=("OWNER_CONFIRMED_DESIGN_INTENT"
                       if f.is_design_authority
                       else "PROVISIONAL_DESIGN_INTENT_NOT_OWNER_CONFIRMED"),
            confirmation_state=f.confirmation_state)
        used_fields.append(f.name)

    payload = repr(sorted((k, repr(v.value), v.origin)
                          for k, v in resolved.items()))
    return {
        "record_type": SCHEMA,
        "concept_reference": intent.concept_reference,
        "intent_identity": intent.identity(),
        "mapping_identity": hashlib.sha256(payload.encode()).hexdigest()[:16],
        "resolved": {k: v.as_dict() for k, v in resolved.items()},
        "conflicts": conflicts,
        "concept_derived_count": sum(
            1 for v in resolved.values() if v.origin != FROM_DEFAULT),
        "generic_default_count": sum(
            1 for v in resolved.values() if v.origin == FROM_DEFAULT),
        "used_intent_fields": sorted(used_fields),
        "unused_intent_fields": sorted(
            f.name for f in intent.fields
            if f.name not in used_fields
            and f.confirmation_state != di.REMOVED),
        "owner_approved": intent.confirmed,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }


def check_engineering(mapping, *, feasibility) -> dict:
    """§J — compare mapped values against engineering limits."""
    conflicts = list(mapping["conflicts"])
    for target, limit in feasibility.items():
        row = mapping["resolved"].get(target)
        if row is None:
            continue
        value = row["value"]
        if not isinstance(value, (int, float)):
            continue
        lo, hi = limit["min"], limit["max"]
        if value < lo or value > hi:
            conflicts.append(PaletteDesignEngineeringConflict(
                design_requirement=f"{target} = {value} "
                                   f"(from {row['source_field'] or 'default'})",
                engineering_conflict=(
                    f"{target} must lie within {lo}..{hi} "
                    f"({limit.get('why', 'engineering limit')})"),
                affected_components=limit.get("components", [target]),
                severity=limit.get("severity", "MAJOR"),
                proposed_alternatives=[
                    f"clamp to the nearest feasible value "
                    f"({lo if value < lo else hi})",
                    "relax the engineering limit (requires owner ruling)",
                    "change the concept expression of this feature"],
                visual_impact=limit.get("visual_impact", "the concept's "
                                        "proportion is not reproduced"),
                dimensional_impact=f"requested {value}, feasible "
                                   f"{lo}..{hi}",
                manufacturing_uncertainty="NOT_ESTABLISHED",
                recommended_resolution="report to the owner; do NOT clamp "
                                       "silently").as_dict())
    return {"record_type": "palette_design_engineering_conflicts/1.0",
            "conflicts": conflicts, "conflict_count": len(conflicts),
            "blocking": [c for c in conflicts
                         if c["severity"] == "BLOCKING"],
            "resolution_policy": "conflicts are reported, never silently "
                                 "resolved; the design is not distorted and "
                                 "the engineering rule is not weakened"}
