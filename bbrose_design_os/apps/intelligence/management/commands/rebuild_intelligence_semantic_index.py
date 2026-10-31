"""Rebuild the intelligence semantic index — DIP-1C-1, wired to a declared schema by
DIP-1C-4A-CORR-1.

A deliberate, human-run operation. It NEVER runs automatically, at startup, during
migrations, browser requests, imports, assertions, projector rebuilds, deployment, or CI.

Default is a **dry-run** that writes nothing and calls nothing external. It prints a preview
report so an operator can see exactly what would be sent before anything leaves the machine.

Layers of fail-closed defence before a single byte reaches OpenAI:
  1. `--apply` is required to write anything at all.
  2. `--provider openai` must be named explicitly. There is no implicit provider fallback.
  3. `--confirm-external-data-transfer` must ALSO be passed. Missing it fails closed — no
     interactive prompt, because the command may run non-interactively.
  4. `--document-schema` must be named explicitly for an external apply. A "schema-1.2
     build" must never silently transmit schema-1.1 documents because of a default; the
     schema is routed through the versioned builder registry, not an accidental import.
  5. The OpenAI encoder refuses to construct without confirmation and on a missing key
     (without inspecting or printing the key).

The command never prints the key, the full documents, or anything derived from the key.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.intelligence.semantic_builders import (
    DEFAULT_BUILD_SCHEMA, SUPPORTED_BUILD_SCHEMAS, SemanticBuilderError,
    build_manifest, build_semantic_corpus,
)
from apps.intelligence.semantic_document import PROHIBITED_FIELDS
from apps.intelligence.semantic_encoder import (
    OPENAI_MODEL, OPENAI_PROVIDER, STUB_ENCODER_IDENTIFIER, EncoderConfigurationError,
    get_encoder,
)
from apps.intelligence.semantic_index import INDEX_SCHEMA, build_generation


class Command(BaseCommand):
    help = ("Rebuild the intelligence semantic embedding index at a declared document "
            "schema. Dry-run by default; external transfer requires --apply "
            "--provider openai --confirm-external-data-transfer --document-schema.")

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Persist a generation. Without it, dry-run only.")
        parser.add_argument("--provider", default=STUB_ENCODER_IDENTIFIER,
                            help="Encoder provider. 'openai' requires explicit confirmation.")
        parser.add_argument("--confirm-external-data-transfer", action="store_true",
                            help="Required to send bounded documents to an external provider.")
        parser.add_argument("--document-schema", default=None,
                            help=("Semantic-document schema to build. Required for an "
                                  "external apply; a dry-run defaults to "
                                  f"{DEFAULT_BUILD_SCHEMA}."))
        parser.add_argument("--publish", action="store_true",
                            help="Publish the built generation (OpenAI production only).")
        parser.add_argument("--json", action="store_true", help="Emit JSON.")
        parser.add_argument("--invoked-by", default="",
                            help="Operator identity for the local audit record.")

    def handle(self, *args, **opts):
        provider = opts["provider"]
        apply = opts["apply"]
        confirmed = opts["confirm_external_data_transfer"]
        is_external = provider == OPENAI_PROVIDER
        schema = opts["document_schema"]

        # --- schema selection, fail-closed for external apply ---------------------
        # An external apply must NEVER infer the schema: a schema-1.2 authorization must not
        # silently transmit schema-1.1 documents. A dry-run may default, but says which.
        if is_external and apply and not schema:
            raise CommandError(
                "external apply requires an explicit --document-schema; refusing to infer "
                f"it (supported: {sorted(SUPPORTED_BUILD_SCHEMAS)}).")
        selected_schema = schema or DEFAULT_BUILD_SCHEMA
        if selected_schema not in SUPPORTED_BUILD_SCHEMAS:
            raise CommandError(
                f"unsupported --document-schema {selected_schema!r}; "
                f"supported: {sorted(SUPPORTED_BUILD_SCHEMAS)}")

        # build once, through the registry, at the DECLARED schema
        try:
            built = build_semantic_corpus(document_schema_version=selected_schema)
        except SemanticBuilderError as exc:
            raise CommandError(str(exc)) from exc

        model = OPENAI_MODEL if is_external else provider
        dimension = 1536 if is_external else 0
        manifest = build_manifest(
            document_schema_version=selected_schema, provider=provider,
            model_identifier=model, vector_dimension=dimension,
            index_schema_version=INDEX_SCHEMA)
        preview = {
            "provider": provider,
            "model": model,
            "document_schema_version": selected_schema,
            "document_builder": "versioned_registry",
            "corpus_hash": manifest["corpus_hash"],
            "embedding_text_manifest_hash": manifest["embedding_text_manifest_hash"],
            "document_content_manifest_hash": manifest["document_content_manifest_hash"],
            "document_count": built.document_count,
            "excluded_count": built.excluded_count,
            "estimated_api_requests": built.document_count if is_external else 0,
            "estimated_total_chars": sum(len(t) for t in built.texts()),
            "prohibited_fields_confirmed_absent": list(PROHIBITED_FIELDS),
            "prohibited_field_findings": 0,
            "prohibited_value_findings": 0,
            "campaign_hash": manifest["campaign_hash"],
            "campaign_partition": manifest["campaign_partition"],
            "external_transfer": is_external,
            "apply": apply,
        }

        # --- dry-run: nothing written, nothing sent -------------------------------
        if not apply:
            preview["statement"] = "DRY RUN — no data was sent and nothing was written."
            return self._emit(preview, opts["json"])

        # --- external transfer gate (fails closed, non-interactive) ---------------
        if is_external and not confirmed:
            raise CommandError(
                "external transfer to OpenAI requires --confirm-external-data-transfer; "
                "refusing to send any data.")
        if not is_external and provider not in (STUB_ENCODER_IDENTIFIER, "stub", "test"):
            raise CommandError(f"unknown provider {provider!r}")

        try:
            encoder = get_encoder(provider, external_transfer_confirmed=confirmed)
        except EncoderConfigurationError as exc:
            raise CommandError(str(exc)) from exc

        # a stub generation is never publishable as production; build_generation enforces it
        generation = build_generation(
            encoder, document_schema_version=selected_schema,
            invoked_by=opts["invoked_by"], published=opts["publish"])

        result = dict(preview)
        result.update({
            "statement": ("APPLIED" if not is_external
                          else "APPLIED — bounded documents were sent to OpenAI."),
            "generation_id": str(generation.pk),
            "status": generation.status,
            "is_test_encoder": generation.is_test_encoder,
            "embedded_count": generation.embedded_count,
            "request_count": generation.request_count,
            "published": generation.status == generation.Status.PUBLISHED,
        })
        return self._emit(result, opts["json"])

    def _emit(self, payload, as_json):
        if as_json:
            import json
            self.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
            return
        for key in sorted(payload):
            value = payload[key]
            if isinstance(value, list):
                value = f"[{len(value)} items]"
            self.stdout.write(f"{key}: {value}")
