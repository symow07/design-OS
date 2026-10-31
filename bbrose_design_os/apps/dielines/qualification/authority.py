"""Qualification authority states (2A-9C slice 0).

Four INDEPENDENT states — technical qualification never implies physical
or production authority, and no state is inferred from another:

    TECHNICALLY_QUALIFIED_DOMAIN            (machine evidence: sweep+matrix)
    PHYSICALLY_VALIDATED_INSTANCE           (one recorded FIT_PASS, per hash)
    PHYSICALLY_VALIDATED_DIMENSIONAL_FAMILY (recorded FIT_PASSes across a
                                             declared family)
    PRODUCTION_AUTHORIZED_BY_MANUFACTURER   (human/manufacturer evidence)

Records are bounded data with mandatory provenance; granting the two
PHYSICALLY_* states requires recorded physical evidence
(apps.dielines.services.physical_validation), and
PRODUCTION_AUTHORIZED_BY_MANUFACTURER is never machine-granted.
"""
from __future__ import annotations

from django.utils import timezone

TECHNICALLY_QUALIFIED_DOMAIN = "TECHNICALLY_QUALIFIED_DOMAIN"
PHYSICALLY_VALIDATED_INSTANCE = "PHYSICALLY_VALIDATED_INSTANCE"
PHYSICALLY_VALIDATED_DIMENSIONAL_FAMILY = \
    "PHYSICALLY_VALIDATED_DIMENSIONAL_FAMILY"
PRODUCTION_AUTHORIZED_BY_MANUFACTURER = \
    "PRODUCTION_AUTHORIZED_BY_MANUFACTURER"

ALL_STATES = (TECHNICALLY_QUALIFIED_DOMAIN, PHYSICALLY_VALIDATED_INSTANCE,
              PHYSICALLY_VALIDATED_DIMENSIONAL_FAMILY,
              PRODUCTION_AUTHORIZED_BY_MANUFACTURER)

#: states a machine may record on the strength of its own evidence
MACHINE_GRANTABLE = frozenset({TECHNICALLY_QUALIFIED_DOMAIN})


class AuthorityError(ValueError):
    pass


def authority_record(*, state: str, archetype_key: str,
                     geometry_hash: str = "",
                     dimensional_family: str = "",
                     board_thickness_mm: float | None = None,
                     validation_source: str,
                     evidence_identity: str,
                     manufacturer: str = "",
                     limitations: list[str] | None = None) -> dict:
    """One bounded authority-state record with mandatory provenance."""
    if state not in ALL_STATES:
        raise AuthorityError(f"unknown authority state {state!r}")
    if not validation_source or not evidence_identity:
        raise AuthorityError(
            "validation_source and evidence_identity are mandatory — an "
            "authority state without provenance is not evidence")
    if state in (PHYSICALLY_VALIDATED_INSTANCE,
                 PHYSICALLY_VALIDATED_DIMENSIONAL_FAMILY) and \
            "FIT_PASS" not in evidence_identity:
        raise AuthorityError(
            f"{state} requires recorded physical FIT_PASS evidence "
            "(physical_validation records)")
    if state == PRODUCTION_AUTHORIZED_BY_MANUFACTURER and not manufacturer:
        raise AuthorityError(
            "PRODUCTION_AUTHORIZED_BY_MANUFACTURER requires the "
            "manufacturer identity")
    return {
        "schema_version": "dieline_authority_record/1.0",
        "state": state,
        "archetype_key": archetype_key,
        "geometry_hash": geometry_hash,
        "dimensional_family": dimensional_family,
        "board_thickness_mm": board_thickness_mm,
        "validation_source": validation_source,
        "manufacturer": manufacturer,
        "evidence_identity": evidence_identity,
        "recorded_at": timezone.now().isoformat(),
        "limitations": list(limitations or ()),
    }


def technical_projection(adapter, *, sweep_seed: int,
                         accepted_commit: str = "") -> dict:
    """The one machine-grantable state, with its evidence identity."""
    return authority_record(
        state=TECHNICALLY_QUALIFIED_DOMAIN,
        archetype_key=adapter.key,
        validation_source="parametric qualification (derived domain + "
                          "seeded property sweep + fixture matrix + "
                          "folded simulation)",
        evidence_identity=f"seed={sweep_seed}"
                          + (f"; commit={accepted_commit}"
                             if accepted_commit else ""),
        limitations=[
            "technical only — grants no physical or production authority",
            "covers only the explicitly derived supported domain",
            "unsupported combinations correctly return "
            "DIMENSION_COMBINATION_UNSUPPORTED",
        ])


__all__ = ["authority_record", "technical_projection", "AuthorityError",
           "ALL_STATES", "MACHINE_GRANTABLE",
           "TECHNICALLY_QUALIFIED_DOMAIN", "PHYSICALLY_VALIDATED_INSTANCE",
           "PHYSICALLY_VALIDATED_DIMENSIONAL_FAMILY",
           "PRODUCTION_AUTHORIZED_BY_MANUFACTURER"]
