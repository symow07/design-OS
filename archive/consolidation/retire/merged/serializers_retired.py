"""The task API serializer's links to the authored masters' files, archived with the Day 4–6 master pages
(the owner's goal of 2026-10-29). Copied whole from bbrose_design_os/apps/pipeline/serializers.py at a634230; kept as text."""

# PackagingOutputSerializer._hybrid_url
    def _hybrid_url(self, obj, role):
        from django.http import Http404
        from django.urls import reverse
        assembly = (obj.spec_sheet or {}).get('backend') == 'hybrid_assembly'
        if assembly:
            from apps.dashboard.assembly_views import artifact_path
            role = 'comparison' if role == 'artwork' else role
        else:
            from apps.dashboard.hybrid_views import artifact_path
        try:
            artifact_path(obj, role)
        except (Http404, KeyError, ValueError, OSError):
            return None
        return reverse('dashboard:assembly_file' if assembly else 'dashboard:hybrid_file', args=[obj.pk, role])
