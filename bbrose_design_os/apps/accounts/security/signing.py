"""HMAC signing and key registry for decision events (DIP-1A-1).

**What the HMAC proves, and what it does not.**

It proves that an event record was produced by an application instance holding an
authorized signing key. It is therefore *tamper evidence*: a row edited directly in the
database — by a DB superuser, by raw SQL, by a restored partial backup — will not verify.

It is **not** a personal signature. It does **not** prove that a particular human held a
private key, and it cannot support non-repudiation: any application instance with the key
can produce any event. Attributing an action to a human rests on the authenticated Django
session and the authorization policy, not on this MAC.

That distinction is written here because it is exactly the kind of thing that gets
quietly upgraded in a summary slide, and then someone believes the database can prove
who approved a licence. It cannot. Per-user asymmetric signing is a separate, planned
milestone.

**Key handling**

* the key is **never** `SECRET_KEY`, never in the database, never in source control;
* the registry is supplied through the environment / secret store;
* **only the active key signs**; previous keys remain **verification-only**, so a
  rotation does not invalidate history;
* an **unknown key id fails closed**;
* a **duplicate key id** or an **active key with no material** fails startup validation —
  a misconfigured signer must not quietly produce unverifiable events.
"""
from __future__ import annotations

import hmac
import json
from hashlib import sha256

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .canonical import canonical_bytes

ALGORITHM = "HMAC-SHA-256"
MIN_KEY_BYTES = 32          # 256 bits. A short MAC key is a decoration.


class SigningConfigurationError(ImproperlyConfigured):
    """The signing configuration is invalid. Events must not be created."""


class UnknownSigningKey(SigningConfigurationError):
    """An event names a key we do not have. FAIL CLOSED — never 'verify anyway'."""


class KeyRegistry:
    """The signing keys: one active, any number of verification-only predecessors."""

    def __init__(self, keys: dict[str, str], active_key_id: str):
        self._validate(keys, active_key_id)
        self._keys = {k: v.encode("utf-8") for k, v in keys.items()}
        self._active = active_key_id

    @staticmethod
    def _validate(keys, active_key_id) -> None:
        if not isinstance(keys, dict) or not keys:
            raise SigningConfigurationError(
                "DECISION_EVENT_HMAC_KEYS must be a non-empty mapping of "
                "{key_id: secret}. Without it, no decision event can be signed.")
        for kid, material in keys.items():
            if not isinstance(kid, str) or not kid:
                raise SigningConfigurationError("every signing key needs a string id")
            if not isinstance(material, str) or not material:
                raise SigningConfigurationError(
                    f"signing key {kid!r} has no key material")
            if len(material.encode("utf-8")) < MIN_KEY_BYTES:
                raise SigningConfigurationError(
                    f"signing key {kid!r} is shorter than {MIN_KEY_BYTES} bytes. A "
                    "short MAC key is a decoration, not a control.")
        if not active_key_id:
            raise SigningConfigurationError(
                "DECISION_EVENT_ACTIVE_KEY_ID is not set — nothing may sign")
        if active_key_id not in keys:
            raise SigningConfigurationError(
                f"the active key id {active_key_id!r} has no key material. FAIL CLOSED: "
                "an active key we do not hold means every new event would be "
                "unverifiable.")

    @property
    def active_key_id(self) -> str:
        return self._active

    @property
    def key_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._keys))

    def material_for(self, key_id: str) -> bytes:
        """Verification key lookup. An unknown id raises — it never falls back."""
        try:
            return self._keys[key_id]
        except KeyError:
            raise UnknownSigningKey(
                f"event names signing key {key_id!r}, which is not in the registry "
                f"(known: {list(self.key_ids)}). FAIL CLOSED — an unverifiable event "
                "is not a valid one.") from None

    # --- signing / verification ---------------------------------------------------
    def sign(self, payload: dict) -> tuple[str, str]:
        """Sign with the ACTIVE key only. Returns (signature, key_id)."""
        kid = self._active
        sig = hmac.new(self._keys[kid], canonical_bytes(payload), sha256).hexdigest()
        return sig, kid

    def verify(self, payload: dict, signature: str, key_id: str) -> bool:
        """Verify with the key the event names — current or retired."""
        expected = hmac.new(self.material_for(key_id), canonical_bytes(payload),
                            sha256).hexdigest()
        # constant-time: a timing oracle on a MAC comparison is a real attack
        return hmac.compare_digest(expected, signature or "")


# --- registry construction from settings -----------------------------------------
_registry: KeyRegistry | None = None


def _load_keys_from_settings() -> tuple[dict, str]:
    raw = getattr(settings, "DECISION_EVENT_HMAC_KEYS", None)
    active = getattr(settings, "DECISION_EVENT_ACTIVE_KEY_ID", None)

    if raw in (None, "", {}):
        raise SigningConfigurationError(
            "DECISION_EVENT_HMAC_KEYS is not configured. Decision events cannot be "
            "signed, and therefore cannot be created. (It is a DEDICATED secret — "
            "never SECRET_KEY, never stored in the database, never committed.)")

    if isinstance(raw, str):
        try:
            keys = json.loads(raw)
        except json.JSONDecodeError as e:
            raise SigningConfigurationError(
                f"DECISION_EVENT_HMAC_KEYS is not valid JSON: {e}") from None
    elif isinstance(raw, dict):
        keys = raw
    else:
        raise SigningConfigurationError(
            "DECISION_EVENT_HMAC_KEYS must be a JSON object or a mapping")

    # A JSON object cannot express a duplicate key — a later one silently wins. Catch
    # it in the raw text, where it is still visible.
    if isinstance(raw, str):
        ids = [k for k, _ in _raw_pairs(raw)]
        dupes = {k for k in ids if ids.count(k) > 1}
        if dupes:
            raise SigningConfigurationError(
                f"duplicate signing key id(s) {sorted(dupes)} — one silently overwrote "
                "another, and events signed with the loser would never verify.")
    return keys, active


def _raw_pairs(raw: str):
    return json.JSONDecoder(object_pairs_hook=lambda pairs: pairs).decode(raw)


def get_registry(*, refresh: bool = False) -> KeyRegistry:
    """The process-wide registry. Raises if the configuration is invalid."""
    global _registry
    if _registry is None or refresh:
        keys, active = _load_keys_from_settings()
        _registry = KeyRegistry(keys, active)
    return _registry


def reset_registry() -> None:
    """Test hook — drop the cached registry so settings overrides take effect."""
    global _registry
    _registry = None


def sign(payload: dict) -> tuple[str, str]:
    return get_registry().sign(payload)


def verify(payload: dict, signature: str, key_id: str) -> bool:
    return get_registry().verify(payload, signature, key_id)


def signing_available() -> tuple[bool, str | None]:
    """Can this instance sign? Used by the system check and the append service."""
    try:
        r = get_registry(refresh=True)
    except SigningConfigurationError as e:
        return False, str(e)
    return True, f"active key {r.active_key_id!r}; {len(r.key_ids)} key(s) known"
