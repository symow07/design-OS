from rest_framework import serializers


class DiеlineSerializer(serializers.Serializer):
    width = serializers.FloatField()
    height = serializers.FloatField()
    depth = serializers.FloatField()
    box_type = serializers.CharField()
    svg = serializers.CharField(read_only=True)
