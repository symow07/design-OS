"""Pluggable embedding encoders — DIP-1C-1.

Two encoders, one interface. The interface is what lets storage migrate to pgvector later
without touching the semantic-document, generation-identity, provider/model, or hybrid
contracts.

* **DeterministicStubEncoder** — local, offline, reproducible. Exists ONLY for tests,
  dry-runs, and architecture verification. It never calls out. Its generations are marked
  ``is_test_encoder=True`` / provider ``TEST_ENCODER_NON_PRODUCTION`` and are barred from
  becoming the production publication. It is deterministic (same document → same vector)
  and content-discriminating (different documents → different vectors) so ranking can be
  tested — but it is never production semantic quality.

* **OpenAIEncoder** — the production-capable path, ``text-embedding-3-small``. It transmits
  the bounded semantic document to OpenAI and is reachable ONLY through the explicit
  human-run ``--apply --provider openai --confirm-external-data-transfer`` command. It never
  runs at startup, during migrations, browser requests, tests, dry-run, Django checks, CI,
  or any automatic path. There is no implicit provider fallback: if OpenAI was not
  explicitly selected, external execution is refused.

The API key is read only from the established secure runtime config, never copied into a
row, log, output, failure summary, or document, and never printed while validating.
"""
from __future__ import annotations

import hashlib
import math
import struct

TEST_ENCODER_PROVIDER = "TEST_ENCODER_NON_PRODUCTION"
STUB_ENCODER_IDENTIFIER = "deterministic_stub"
STUB_ENCODER_VERSION = "intelligence_stub_encoder/1.0"
STUB_DIMENSION = 64

OPENAI_PROVIDER = "openai"
OPENAI_ENCODER_IDENTIFIER = "openai_embeddings"
OPENAI_MODEL = "text-embedding-3-small"
OPENAI_ENCODER_VERSION = "intelligence_openai_encoder/1.0"
OPENAI_DIMENSION = 1536


class EncoderConfigurationError(RuntimeError):
    """Raised when an encoder cannot run safely — e.g. a missing key on an explicit apply.
    Fails closed; never falls back to another provider."""


def vector_hash(vector) -> str:
    packed = b"".join(struct.pack("<d", float(x)) for x in vector)
    return hashlib.sha256(packed).hexdigest()


class BaseEncoder:
    provider: str
    encoder_identifier: str
    encoder_version: str
    model_identifier: str
    dimension: int
    is_test_encoder: bool

    def encode(self, texts):                       # pragma: no cover - interface
        raise NotImplementedError


class DeterministicStubEncoder(BaseEncoder):
    """Offline, reproducible, content-discriminating. Never production quality."""
    provider = TEST_ENCODER_PROVIDER
    encoder_identifier = STUB_ENCODER_IDENTIFIER
    encoder_version = STUB_ENCODER_VERSION
    model_identifier = STUB_ENCODER_IDENTIFIER
    dimension = STUB_DIMENSION
    is_test_encoder = True

    def _one(self, text):
        # hash tokens into a stable float vector: same text -> same vector (idempotent),
        # different text -> different vector (so ranking is meaningfully testable)
        vector = [0.0] * self.dimension
        tokens = (text or "").lower().split()
        for token in tokens or [""]:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(self.dimension):
                byte = digest[i % len(digest)]
                vector[i] += (byte - 127.5) / 127.5
        norm = math.sqrt(sum(c * c for c in vector))
        if norm == 0:
            vector[0] = 1.0
            norm = 1.0
        return [c / norm for c in vector]

    def encode(self, texts):
        return [self._one(t) for t in texts]


class OpenAIEncoder(BaseEncoder):
    """Production-capable. Transmits bounded documents to OpenAI. Explicit apply only."""
    provider = OPENAI_PROVIDER
    encoder_identifier = OPENAI_ENCODER_IDENTIFIER
    encoder_version = OPENAI_ENCODER_VERSION
    model_identifier = OPENAI_MODEL
    dimension = OPENAI_DIMENSION
    is_test_encoder = False

    def __init__(self, *, external_transfer_confirmed: bool):
        # a structural guard: the OpenAI encoder cannot even be constructed without the
        # explicit external-transfer acknowledgement, so no code path can call out by
        # accident
        if not external_transfer_confirmed:
            raise EncoderConfigurationError(
                "external data transfer not confirmed; refusing to construct OpenAIEncoder")
        from django.conf import settings
        key = getattr(settings, "OPENAI_API_KEY", "") or ""
        if not key.strip():
            # fail closed on a missing key — do not inspect or print it
            raise EncoderConfigurationError(
                "OPENAI_API_KEY is not configured; refusing external embedding build")
        self._external_transfer_confirmed = True

    def encode(self, texts):
        from django.conf import settings
        from openai import OpenAI
        raise EncoderConfigurationError('Paid semantic embedding builds are paused during the rescue until their budget integration is verified.')
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        vectors = []
        for text in texts:
            response = client.embeddings.create(model=self.model_identifier, input=text)
            vectors.append(list(response.data[0].embedding))
        return vectors


def get_encoder(provider, *, external_transfer_confirmed=False) -> BaseEncoder:
    """Resolve an encoder by explicit provider name. No implicit default to OpenAI."""
    if provider in (TEST_ENCODER_PROVIDER, STUB_ENCODER_IDENTIFIER, "stub", "test"):
        return DeterministicStubEncoder()
    if provider == OPENAI_PROVIDER:
        return OpenAIEncoder(external_transfer_confirmed=external_transfer_confirmed)
    raise EncoderConfigurationError(f"unknown or unselected encoder provider {provider!r}")
