from rest_framework import serializers
from .models import (
    AgentLog,
    CreativeBrief,
    DesignTask,
    GateDecision,
    GeneratedImage,
    PackagingOutput,
)


class CreativeBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreativeBrief
        fields = ['id', 'directions', 'design_intent', 'selected_direction_id',
                  'direction_selected_at', 'retrieved_products',
                  'retrieved_references', 'created_at']


class TaskListItemSerializer(serializers.ModelSerializer):
    """Compact row for the paginated task-list API (Milestone 13.2)."""
    task_text = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)
    created_by = serializers.CharField(source='created_by.username', read_only=True, default=None)

    def get_task_text(self, obj):
        return obj.task_text[:80]

    class Meta:
        model = DesignTask
        fields = ['id', 'task_text', 'status', 'product_name',
                  'created_by', 'brand_id', 'created_at']


class AgentLogSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    # §BH54(k) 1: what the row carries, as one compact line — scalars by name, collections by their size — with
    # path-like tokens removed (the stance of reconstruction_status: no filesystem path reaches the browser)
    detail = serializers.SerializerMethodField()
    # §BH55 Phase 3: who is working and what is being done, in a designer's words (apps/pipeline/feed_words.py); the
    # row itself — agent_name, action — is carried unchanged beside them
    who = serializers.SerializerMethodField()
    said = serializers.SerializerMethodField()

    def get_actor(self, obj):
        return obj.actor.username if obj.actor else None

    def get_who(self, obj):
        from apps.pipeline.feed_words import who
        return who(obj.agent_name)

    def get_said(self, obj):
        from apps.pipeline.feed_words import said
        return said(obj.action)

    def get_detail(self, obj):
        import re
        payload = obj.payload
        if not isinstance(payload, dict) or not payload:
            return ''
        parts = []
        for key, value in sorted(payload.items()):      # jsonb keeps no insertion order: by name, so the line is stable
            if isinstance(value, (list, dict)):
                parts.append(f"{key}: {len(value)} item{'' if len(value) == 1 else 's'}")
            elif value not in (None, ''):
                parts.append(f"{key}: {str(value)[:60]}")
        return re.sub(r'(/[\w.\-]+){2,}', '[path removed]', ' · '.join(parts))[:240]

    class Meta:
        model = AgentLog
        fields = ['id', 'agent_name', 'action', 'level', 'actor', 'timestamp', 'detail', 'who', 'said']


class GateDecisionSerializer(serializers.ModelSerializer):
    decided_by = serializers.SerializerMethodField()

    def get_decided_by(self, obj):
        return obj.decided_by.username if obj.decided_by else None

    class Meta:
        model = GateDecision
        fields = ['id', 'gate', 'decision', 'notes', 'decided_by', 'decided_at']


class GeneratedImageSerializer(serializers.ModelSerializer):
    image_url_display = serializers.SerializerMethodField()
    qa_notes_parsed = serializers.SerializerMethodField()
    direction_sentence = serializers.SerializerMethodField()
    selectable = serializers.SerializerMethodField()
    quality_review = serializers.SerializerMethodField()

    def get_selectable(self, obj):
        from apps.pipeline.services.gate1_review import image_is_selectable
        return image_is_selectable(obj, verify_pixels=True)

    def get_quality_review(self, obj):
        from apps.pipeline.services.concept_quality import image_verdict
        return image_verdict(obj)


    def get_direction_sentence(self, obj):
        """[His final goal, 2026-10-05, B4: "Each picture shows a name and one sentence; the details folded."] The first
        sentence of the concept of the direction this picture was drawn for."""
        import re
        if not obj.direction_id:
            return ""
        brief = CreativeBrief.objects.filter(task_id=obj.task_id).first()
        found = next((d for d in (brief.directions or []) if d.get("direction_id") == obj.direction_id),
                     None) if brief else None
        words = " ".join(str((found or {}).get("concept_statement") or "").split())
        first = re.match(r"(.+?[.!?])(\s|$)", words)
        return first.group(1) if first else words

    def get_image_url_display(self, obj):
        if (obj.reference_provenance or {}).get('kind') == 'authored_master_snapshot':
            output = PackagingOutput.objects.filter(approved_image=obj).first()
            return PackagingOutputSerializer._hybrid_url(self, output, 'artwork') if output else None
        # Only ever serve the locally stored copy (via the authenticated media
        # route or a signed S3 URL). NEVER fall back to obj.image_url — that is
        # the provider's unauthenticated signed URL and expires in ~1h
        # (Milestone 8.6 / audit H1). None → the frontend renders a retryable
        # "image unavailable" placeholder using download_failed.
        if obj.image_file:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.image_file.url) if request else obj.image_file.url
        return None

    def get_qa_notes_parsed(self, obj):
        import json
        try:
            return json.loads(obj.qa_notes) if obj.qa_notes else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    class Meta:
        model = GeneratedImage
        # prompt_used is exposed so reviewers can edit prompts at Gate 1
        # ("Edit & re-run", Milestone 11.3); superseded lets clients render the
        # history behind a toggle. reference_provenance backs the Review
        # Board's MATERIAL REFERENCES USED section (2A-6E §8): what actually
        # reached the provider for this render — an image must never claim
        # material influence this field does not evidence.
        fields = ['id', 'direction_name', 'direction_id', 'direction_sentence', 'prompt_used', 'image_url_display',
                  'variation_number', 'qa_passed', 'qa_notes_parsed', 'selectable', 'quality_review',
                  'is_approved', 'superseded', 'download_failed',
                  'user_rejection_label', 'reference_provenance', 'created_at']


class ConceptReferenceSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    production_use_allowed = serializers.ReadOnlyField()
    concept_reference_only = serializers.SerializerMethodField()
    # §BH55 Phase 3: what the materials record says of this file, and what it shows — the picker offered a file with
    # neither (survey rows 1.11, 3.9)
    record = serializers.SerializerMethodField()

    def get_record(self, obj):
        from apps.dashboard.materials_library import record_of
        try:
            return record_of(obj)
        except Exception:      # noqa: BLE001 — a record that cannot be read never hides the reference itself
            return {}

    def get_thumbnail_url(self, obj):
        from django.urls import reverse
        url = reverse('pipeline:concept_reference_thumbnail', args=[obj.pk])
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url

    def get_concept_reference_only(self, obj):
        return obj.permission_status == obj.PERMISSION_APPROVED

    class Meta:
        from apps.pipeline.models import ConceptReference
        model = ConceptReference
        fields = ['id', 'source_type', 'library_item_id', 'title',
                  'description', 'relevance_reason', 'retrieval_score',
                  'ownership_status', 'rights_status', 'is_vector',
                  'permission_status', 'production_use_allowed',
                  'concept_reference_only', 'thumbnail_url', 'created_at', 'record']


class PackagingOutputSerializer(serializers.ModelSerializer):
    dieline_svg_url = serializers.SerializerMethodField()
    dieline_ai_url = serializers.SerializerMethodField()
    production_pdf_url = serializers.SerializerMethodField()

    def get_dieline_svg_url(self, obj):
        return obj.dieline_file.url if obj.dieline_file else None

    def get_dieline_ai_url(self, obj):
        return obj.dieline_ai_file.url if obj.dieline_ai_file else None

    def get_production_pdf_url(self, obj):
        return obj.production_pdf.url if obj.production_pdf else None

    design_preview_url = serializers.SerializerMethodField()
    design_preview_ai_url = serializers.SerializerMethodField()
    design_inside_url = serializers.SerializerMethodField()
    label_offers = serializers.SerializerMethodField()
    native_ai_url = serializers.SerializerMethodField()
    self_check = serializers.SerializerMethodField()

    def get_self_check(self, obj):
        """[His final goal, 2026-10-05, C7] what the drawing's own check fixed and what it shows him."""
        record = (obj.spec_sheet or {}).get('self_check/1.0') or {}
        return {"said": record.get("said") or [], "clean": record.get("clean"),
                "fixed": len(record.get("fixed") or []), "shown": len(record.get("shown") or [])} if record else None

    designers_eye = serializers.SerializerMethodField()

    def get_designers_eye(self, obj):
        """[His goal for the pitch, 2026-10-15, B (5): "Tell me the cost per design."] the designer's eye's verdict on
        the drawing beside its concept: PASS or what it still sees, its fixes, its looks and what it cost."""
        record = (obj.spec_sheet or {}).get('designers_eye/1.0') or {}
        if not record:
            return None
        return {"state": record.get("state"), "summary": record.get("summary") or "",
                "looks": len(record.get("rounds") or []), "fixed": record.get("fixed") or [],
                "left": [{"part": d.get("part"), "severity": d.get("severity"), "concept": d.get("concept"),
                          "drawing": d.get("drawing")} for d in record.get("left") or []],
                "cost_usd": record.get("cost_usd") or "0"}

    def get_native_ai_url(self, obj):
        """[His final goal, 2026-10-05, C6] the native, layered .ai, where Illustrator built it."""
        from django.core.files.storage import default_storage
        record = (obj.spec_sheet or {}).get('native_ai/1.0') or {}
        return default_storage.url(record['path']) if record.get('built') and record.get('path') else None

    other_files = serializers.SerializerMethodField()

    def get_other_files(self, obj):
        """[D-D11-9; his goal of 2026-10-13, (5): "one 'Download' (the layered .ai, with other formats in a small
        menu)"] a published master's other files — each piece's own .ai or PDF, its 1 : 1 sheets, the day's records —
        each in its words, for the "Other formats" menu after the fixed formats (``services.master_tasks``,
        ``downloads/1.0``); [] for every other design."""
        from django.core.files.storage import default_storage
        return [{'url': default_storage.url(row['path']), 'words': row['words']}
                for row in (obj.spec_sheet or {}).get('downloads/1.0') or [] if row.get('path')]

    def get_label_offers(self, obj):
        """[His final goal, 2026-10-05, C5] a stopped label's offers, each with its pictures' addresses."""
        from django.core.files.storage import default_storage
        out = []
        spec = obj.spec_sheet or {}
        # [his final goal, C5c] a container's stopped back offers its own, drawn the same way
        for row in (spec.get('label_offers/1.0') or []) + (spec.get('container_label_offers/1.0') or []):
            out.append(dict(row, **{k + '_url': default_storage.url(row[k]) for k in ('png', 'png_inside', 'ai')
                                     if row.get(k)}))
        return out

    def get_design_inside_url(self, obj):
        """[His final goal, 2026-10-05, B1: "Two artboards, OUTSIDE and INSIDE."] the inside artboard's picture."""
        from django.core.files.storage import default_storage
        name = ((obj.spec_sheet or {}).get('inside_print/1.0') or {}).get('preview')
        return default_storage.url(name) if name else None

    def _container_result(self, obj):
        """VQR-6: for Product Container outputs the reconstruction RESULT
        CONTRACT is the only availability authority — a truthy FieldFile is
        not proof its storage object is available, authorized or valid.
        Memoized per serialization; None for other targets."""
        if obj.task.design_target != 'product_container':
            return None
        if not hasattr(self, '_vqr6_result_cache'):
            self._vqr6_result_cache = {}
        if obj.pk not in self._vqr6_result_cache:
            from apps.pipeline.services.reconstruction_status import (
                build_container_reconstruction_result)
            self._vqr6_result_cache[obj.pk] = \
                build_container_reconstruction_result(obj.task)
        return self._vqr6_result_cache[obj.pk]

    def get_design_preview_url(self, obj):
        if (obj.spec_sheet or {}).get('backend') in ('hybrid_bottle','hybrid_assembly'):
            return self._hybrid_url(obj, 'comparison')
        # PNG snapshot of the editable .ai (SVG policy: no user-facing SVG).
        if obj.task.design_target == 'product_container':
            result = self._container_result(obj)
            png = result and result['artifacts']['png']
            return png['preview_url'] if png and png['available'] else None
        return obj.design_preview.url if obj.design_preview else None

    def get_design_preview_ai_url(self, obj):
        if (obj.spec_sheet or {}).get('backend') == 'hybrid_assembly':
            return None  # Day 3 provides SVG/PDF geometry, not native Illustrator.
        if (obj.spec_sheet or {}).get('backend') == 'hybrid_bottle':
            return self._hybrid_url(obj, 'ai')
        if obj.task.design_target == 'product_container':
            result = self._container_result(obj)
            ai = result and result['artifacts']['ai']
            return ai['download_url'] if ai and ai['available'] else None
        return obj.design_preview_ai.url if obj.design_preview_ai else None

    def _hybrid_url(self, obj, role):
        # the authored masters' file routes (stand-master/files/, serum-master/files/) retired with their pages on
        # 2026-10-29 (archive/consolidation/retire/merged/serializers_retired.py): no link is offered
        return None

    class Meta:
        model = PackagingOutput
        fields = ['id', 'spec_sheet', 'pacdora_render_url',
                  'dieline_svg_url', 'dieline_ai_url', 'production_pdf_url',
                  'design_preview_url', 'design_preview_ai_url', 'design_inside_url', 'label_offers', 'native_ai_url',
                  'other_files', 'self_check', 'designers_eye',
                  'is_final_approved', 'created_at']


class DesignTaskSerializer(serializers.ModelSerializer):
    logs = AgentLogSerializer(many=True, read_only=True)
    brief = CreativeBriefSerializer(read_only=True)
    images = GeneratedImageSerializer(many=True, read_only=True)
    packaging_outputs = PackagingOutputSerializer(many=True, read_only=True)
    gate_decisions = GateDecisionSerializer(many=True, read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)
    created_by = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    cost_usd = serializers.SerializerMethodField()
    gate_1_set_status = serializers.SerializerMethodField()
    gate_1_map_stop = serializers.SerializerMethodField()

    def get_gate_1_set_status(self, obj):
        # 2B-3V §7: computed set-level rejection banner (None unless every
        # active Gate-1 image is labelled REJECTED). No model field — a later
        # authorized regeneration clears it automatically.
        from apps.pipeline.services.gate1_review import gate1_set_status
        return gate1_set_status(obj)

    def get_created_by(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_assigned_to(self, obj):
        return obj.assigned_to.username if obj.assigned_to else None

    def get_gate_1_map_stop(self, obj):
        # [the owner's finding on design 119, 2026-10-03: "STOP and tell me why, with options"] the concept the design
        # stopped at, why, each part that would not be drawn, and his options — while the design waits at Gate 1
        from apps.pipeline.services import concept_design_map as dm
        if obj.status != "awaiting_gate_1":
            return None
        stops = [(img, (img.reference_provenance or {}).get(dm.MAP_STOP_KEY))
                 for img in obj.images.filter(superseded=False)]
        stops = [(img, stop) for img, stop in stops if isinstance(stop, dict)]
        if not stops:
            return None
        img, stop = max(stops, key=lambda pair: pair[1]["at"])
        return {"image_id": img.pk, "direction_name": img.direction_name, **stop}

    def get_cost_usd(self, obj):
        # Milestone 12.2 — accumulated AI spend for this task, shown on the card.
        from apps.pipeline.services.cost_ledger import task_cost_usd
        return float(task_cost_usd(obj))

    class Meta:
        model = DesignTask
        fields = ['id', 'task_text', 'status', 'created_at', 'updated_at',
                  'gate_1_notes', 'gate_2_notes', 'error_message', 'product_name',
                  'created_by', 'assigned_to', 'image_rerun_count', 'cost_usd',
                  'gate_1_set_status', 'gate_1_map_stop',
                  'brief', 'logs', 'images', 'packaging_outputs', 'gate_decisions']
