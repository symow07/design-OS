from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import DesignTask, GeneratedImage, PackagingOutput
from .serializers import DesignTaskSerializer
from apps.core.models import Brand, Product, Campaign


class TaskCreateView(APIView):
    """POST /api/tasks/create/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        task_text = request.data.get('task_text', '').strip()
        if not task_text:
            return Response({'error': 'task_text is required'}, status=status.HTTP_400_BAD_REQUEST)

        brand = Brand.objects.first()
        if not brand:
            return Response({'error': 'No brand configured. Run seed_bbrose first.'}, status=status.HTTP_400_BAD_REQUEST)

        product = None
        product_id = request.data.get('product_id')
        if product_id:
            product = get_object_or_404(Product, id=product_id, brand=brand)

        campaign = None
        campaign_id = request.data.get('campaign_id')
        if campaign_id:
            campaign = get_object_or_404(Campaign, id=campaign_id, brand=brand)

        task = DesignTask.objects.create(
            brand=brand,
            product=product,
            campaign=campaign,
            task_text=task_text,
            status='queued'
        )

        from .tasks import run_aria_pipeline
        run_aria_pipeline.delay(task.id)

        return Response({'task_id': task.id, 'status': task.status}, status=status.HTTP_201_CREATED)


class TaskStatusView(APIView):
    """GET /api/tasks/<task_id>/status/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id)
        logs = task.logs.order_by('-timestamp')[:20]
        images = task.images.all()
        packaging = task.packaging_outputs.first()

        from .serializers import AgentLogSerializer, GeneratedImageSerializer, PackagingOutputSerializer
        return Response({
            'id': task.id,
            'status': task.status,
            'task_text': task.task_text,
            'product_name': task.product.name if task.product else None,
            'logs': AgentLogSerializer(logs, many=True).data,
            'images': GeneratedImageSerializer(images, many=True, context={'request': request}).data,
            'packaging_output': PackagingOutputSerializer(packaging).data if packaging else None,
            'gate_1_notes': task.gate_1_notes,
            'gate_2_notes': task.gate_2_notes,
        })


class Gate1ApproveView(APIView):
    """POST /api/tasks/<task_id>/gate1_approve/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id, status='awaiting_gate_1')
        image_id = request.data.get('image_id')
        if not image_id:
            return Response({'error': 'image_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        get_object_or_404(GeneratedImage, id=image_id, task=task)

        # Set the intermediate status BEFORE enqueueing so that in DEBUG eager
        # mode (resume runs inline) the resume's status advance isn't clobbered.
        task.status = 'gate_1_approved'
        task.save(update_fields=['status'])
        from .tasks import resume_aria_gate1
        resume_aria_gate1.delay(task.id, image_id)
        task.refresh_from_db()

        return Response({'status': task.status, 'message': 'Gate 1 approved. Generating packaging output.'})


class Gate1RejectView(APIView):
    """POST /api/tasks/<task_id>/gate1_reject/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id, status='awaiting_gate_1')
        notes = request.data.get('notes', '').strip()
        if not notes:
            return Response({'error': 'notes are required when rejecting'}, status=status.HTTP_400_BAD_REQUEST)

        task.gate_1_notes = notes
        task.status = 'queued'
        task.save(update_fields=['gate_1_notes', 'status'])

        from .tasks import run_aria_pipeline
        run_aria_pipeline.delay(task.id)

        return Response({'status': task.status, 'message': 'Sent back to ARIA with revision notes.'})


class Gate2ApproveView(APIView):
    """POST /api/tasks/<task_id>/gate2_approve/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id, status='awaiting_gate_2')
        packaging_output_id = request.data.get('packaging_output_id')
        if not packaging_output_id:
            return Response({'error': 'packaging_output_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        task.status = 'gate_2_approved'
        task.save(update_fields=['status'])
        from .tasks import resume_aria_gate2
        resume_aria_gate2.delay(task.id, packaging_output_id)
        task.refresh_from_db()

        return Response({'status': task.status, 'message': 'Gate 2 approved. Generating spec sheet PDF.'})


class ConfirmDimensionsView(APIView):
    """POST /api/tasks/<task_id>/confirm_dimensions/

    The dimension gate (dieline backend). Validates the confirmed carton
    dimensions, then runs the deterministic geometry + SVG/AI export.
    Body: {"dimensions": {width_mm, depth_mm, height_mm,
                          bleed_mm?, safe_margin_mm?, glue_tab_mm?}}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id, status='awaiting_dimensions')
        output = task.packaging_outputs.filter(dieline_job__isnull=False).first()
        if not output:
            return Response(
                {'error': 'No dieline job for this task. Re-run from Gate 1.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dims = request.data.get('dimensions') or {}
        try:
            confirmed = {
                'width_mm': float(dims['width_mm']),
                'depth_mm': float(dims['depth_mm']),
                'height_mm': float(dims['height_mm']),
                'bleed_mm': float(dims.get('bleed_mm', 3.0)),
                'safe_margin_mm': float(dims.get('safe_margin_mm', 4.0)),
                'glue_tab_mm': float(dims.get('glue_tab_mm', 10.0)),
            }
        except (KeyError, TypeError, ValueError):
            return Response(
                {'error': 'width_mm, depth_mm and height_mm are required numbers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate ranges/structural rules up front so the user gets an
        # immediate, specific error instead of a failed pipeline run.
        from pydantic import ValidationError
        from apps.dielines.validators.schema import DielineInputJSON
        try:
            DielineInputJSON(
                template='straight_tuck_end_carton', unit='mm',
                dimensions={k: confirmed[k] for k in ('width_mm', 'depth_mm', 'height_mm')},
                print_settings={'bleed_mm': confirmed['bleed_mm'],
                                'safe_margin_mm': confirmed['safe_margin_mm']},
                construction={'glue_tab_mm': confirmed['glue_tab_mm']},
                metadata={'product_name': 'validation', 'product_type': 'carton'},
            )
        except ValidationError as exc:
            return Response(
                {'error': 'Invalid dimensions', 'details': exc.errors()},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task.status = 'generating_dieline'
        task.save(update_fields=['status'])
        from .tasks import resume_aria_dimensions
        resume_aria_dimensions.delay(task.id, output.id, confirmed)
        task.refresh_from_db()

        return Response({'status': task.status, 'message': 'Dimensions confirmed. Generating dieline.'})


class TaskRetryView(APIView):
    """POST /api/tasks/<task_id>/retry/ — restart a failed task"""
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id, status='failed')
        task.status = 'queued'
        task.save(update_fields=['status'])

        from .tasks import run_aria_pipeline
        run_aria_pipeline.delay(task.id)
        return Response({'status': task.status, 'message': 'Task requeued.'})


class TaskListView(APIView):
    """GET /api/tasks/ — all tasks paginated"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tasks = DesignTask.objects.order_by('-created_at')[:50]
        return Response([{
            'id': t.id,
            'task_text': t.task_text[:80],
            'status': t.status,
            'product_name': t.product.name if t.product else None,
            'created_at': t.created_at.isoformat(),
        } for t in tasks])


class SpecSheetDownloadView(APIView):
    """GET /api/tasks/<task_id>/download_spec/ — return the spec-sheet PDF."""
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        import os
        from django.http import FileResponse, Http404
        task = get_object_or_404(DesignTask, id=task_id)
        output = task.packaging_outputs.filter(is_final_approved=True).first()
        if not output:
            raise Http404('No approved packaging output for this task')
        if not output.spec_pdf:
            from apps.pipeline.services.spec_sheet import generate_spec_sheet
            generate_spec_sheet(output)
            output.refresh_from_db()
        return FileResponse(
            output.spec_pdf.open('rb'),
            content_type='application/pdf',
            as_attachment=True,
            filename=os.path.basename(output.spec_pdf.name),
        )
