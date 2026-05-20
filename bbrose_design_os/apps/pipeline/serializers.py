from rest_framework import serializers
from .models import DesignTask, AgentLog, GeneratedImage, PackagingOutput, CreativeBrief


class AgentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentLog
        fields = ['id', 'agent_name', 'action', 'level', 'timestamp']


class GeneratedImageSerializer(serializers.ModelSerializer):
    image_url_display = serializers.SerializerMethodField()
    qa_notes_parsed = serializers.SerializerMethodField()

    def get_image_url_display(self, obj):
        if obj.image_file:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.image_file.url) if request else obj.image_file.url
        return obj.image_url

    def get_qa_notes_parsed(self, obj):
        import json
        try:
            return json.loads(obj.qa_notes) if obj.qa_notes else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    class Meta:
        model = GeneratedImage
        fields = ['id', 'direction_name', 'image_url_display', 'variation_number',
                  'qa_passed', 'qa_notes_parsed', 'is_approved', 'created_at']


class PackagingOutputSerializer(serializers.ModelSerializer):
    dieline_svg_url = serializers.SerializerMethodField()
    dieline_ai_url = serializers.SerializerMethodField()

    def get_dieline_svg_url(self, obj):
        return obj.dieline_file.url if obj.dieline_file else None

    def get_dieline_ai_url(self, obj):
        return obj.dieline_ai_file.url if obj.dieline_ai_file else None

    class Meta:
        model = PackagingOutput
        fields = ['id', 'spec_sheet', 'pacdora_render_url',
                  'dieline_svg_url', 'dieline_ai_url',
                  'is_final_approved', 'created_at']


class DesignTaskSerializer(serializers.ModelSerializer):
    logs = AgentLogSerializer(many=True, read_only=True)
    images = GeneratedImageSerializer(many=True, read_only=True)
    packaging_outputs = PackagingOutputSerializer(many=True, read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)

    class Meta:
        model = DesignTask
        fields = ['id', 'task_text', 'status', 'created_at', 'updated_at',
                  'gate_1_notes', 'gate_2_notes', 'product_name',
                  'logs', 'images', 'packaging_outputs']
