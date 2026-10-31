"""PALT-M4B-A3M §2 — separated identity semantics.

A3F changed candidate C's identity string by adding a default-valued
config key, even though the mesh was byte-identical. The owner's ruling is
that default-valued keys must NOT be stripped to restore a historical
hash; the identities must instead be separated by what they actually
describe.

``MESH_GEOMETRY_IDENTITY``
    canonical vertices, faces, winding and quantization only. Two
    byte-equivalent canonical meshes hash the same regardless of how they
    were constructed or what the contract said.
``CONSTRUCTION_CONTRACT_IDENTITY``
    the contract, topology constants, offset mode and target, conventions,
    algorithms, DEFAULT-VALUED KEYS, provenance and authority. Changing an
    algorithm declaration changes this even when the mesh does not move.
``EVIDENCE_PACKAGE_IDENTITY``
    geometry + contract + measurement-authority version + diagnostic
    manifest + rendered evidence hashes.

Historical identities are recorded as legacy aliases. No prior record is
rewritten.
"""
from __future__ import annotations

import hashlib

import numpy as np

SCHEMA = "palette_identity/1.0"

GEOMETRY_SCHEMA = "mesh_geometry_identity/1.0"
CONTRACT_SCHEMA = "construction_contract_identity/1.0"
EVIDENCE_SCHEMA = "evidence_package_identity/1.0"

QUANTIZATION = 1e-6


def _h(payload):
    return hashlib.sha256(payload).hexdigest()[:16]


def mesh_geometry_identity(mesh, *, quantization=QUANTIZATION) -> str:
    """Canonical geometry only — construction metadata takes no part."""
    v = np.asarray(mesh["vertices"], float)
    f = np.asarray(mesh["faces"], np.int64)
    q = np.round(v / quantization).astype(np.int64)
    return _h(q.tobytes() + f.tobytes()
              + f"|{GEOMETRY_SCHEMA}|{quantization}".encode())


def construction_contract_identity(contract) -> str:
    """Everything declared about HOW the mesh was made, defaults included."""
    return _h((repr(_canonical(contract)) + f"|{CONTRACT_SCHEMA}").encode())


def evidence_package_identity(geometry_id, contract_id, *,
                              authority_version, diagnostics,
                              pixel_hashes=None) -> str:
    payload = (f"{geometry_id}|{contract_id}|{authority_version}|"
               f"{repr(sorted(diagnostics))}|"
               f"{repr(_canonical(pixel_hashes or {}))}|{EVIDENCE_SCHEMA}")
    return _h(payload.encode())


def _canonical(obj):
    if isinstance(obj, dict):
        return [(str(k), _canonical(obj[k])) for k in sorted(obj, key=str)]
    if isinstance(obj, (list, tuple)):
        return [_canonical(x) for x in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return _canonical(obj.tolist())
    if isinstance(obj, float):
        return round(obj, 9)
    return obj


def migration_entry(*, old_identity, mesh, contract, geometry_changed,
                    reason, milestone, compatibility="TRACEABLE") -> dict:
    return {
        "old_identity": old_identity,
        "mesh_geometry_identity": mesh_geometry_identity(mesh),
        "construction_contract_identity":
            construction_contract_identity(contract),
        "geometry_changed": bool(geometry_changed),
        "reason": reason,
        "milestone": milestone,
        "compatibility": compatibility,
        "legacy_alias": old_identity,
    }


def migration_map(entries) -> dict:
    return {"record_type": "identity_migration_map/1.0",
            "schemas": {"geometry": GEOMETRY_SCHEMA,
                        "contract": CONTRACT_SCHEMA,
                        "evidence": EVIDENCE_SCHEMA},
            "policy": "default-valued keys are NEVER stripped to restore a "
                      "historical hash; identities are separated instead",
            "entries": entries}
