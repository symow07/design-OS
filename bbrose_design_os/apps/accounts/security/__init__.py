"""Decision-event security primitives (DIP-1A-1).

Canonical serialization, SHA-256 content hashing, HMAC signing and key management.
No models, no migrations — these are the pure foundations everything later signs.
"""
from .canonical import (  # noqa: F401
    CanonicalizationError,
    SCHEMA_VERSION,
    SIGNED_FIELDS,
    canonical_bytes,
    content_hash,
    signed_head_payload,
    signed_payload,
)
from .signing import (  # noqa: F401
    ALGORITHM,
    SigningConfigurationError,
    UnknownSigningKey,
    get_registry,
    sign,
    signing_available,
    verify,
)
