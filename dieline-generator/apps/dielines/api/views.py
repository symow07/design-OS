from __future__ import annotations

import logging

from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from pydantic import ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dielines.api.payloads import build_generate_success_payload
from apps.dielines.exporters.ai_exporter import export_ai
from apps.dielines.exporters.svg_exporter import export_svg, write_svg
from apps.dielines.exporters.svg_validator import validate_ai, validate_svg
from apps.dielines.geometry.engine import calculate_straight_tuck_end
from apps.dielines.models import DielineJob
from apps.dielines.validators.schema import DielineInputJSON

logger = logging.getLogger(__name__)

_INSPIRATION_LIMIT = 5


class GenerateDielineView(LoginRequiredMixin, APIView):
    """
    POST /api/dielines/generate/

    Called after the user confirms all dimensions in the dashboard form.
    Runs the geometry engine and SVG exporter, then updates the DielineJob.
    """

    def post(self, request):
        job_id = request.data.get("job_id")
        if not job_id:
            return Response(
                {"error": "job_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Load DielineJob
        try:
            job = DielineJob.objects.get(pk=job_id)
        except DielineJob.DoesNotExist:
            raise Http404(f"DielineJob {job_id} not found")

        # 2 & 3. Build and validate DielineInputJSON
        dims = request.data.get("confirmed_dimensions", {})
        meta = request.data.get("metadata", {})

        try:
            params = DielineInputJSON(
                template="straight_tuck_end_carton",
                unit="mm",
                dimensions={
                    "width_mm":  dims.get("width_mm"),
                    "depth_mm":  dims.get("depth_mm"),
                    "height_mm": dims.get("height_mm"),
                },
                print_settings={
                    "bleed_mm":        dims.get("bleed_mm"),
                    "safe_margin_mm":  dims.get("safe_margin_mm"),
                },
                construction={
                    "glue_tab_mm":    dims.get("glue_tab_mm"),
                },
                metadata={
                    "product_name": meta.get("product_name", ""),
                    "product_type": meta.get("product_type", ""),
                    "notes":        meta.get("notes", ""),
                },
            )
        except ValidationError as exc:
            return Response(
                {"error": "Invalid dimensions", "details": exc.errors()},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Geometry engine
        try:
            coords = calculate_straight_tuck_end(params)
        except ValueError as exc:
            logger.error("Geometry engine error for job %s: %s", job_id, exc)
            return Response(
                {"error": "Geometry calculation failed", "detail": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # 5. SVG generation
        try:
            svg_string = export_svg(coords, str(job_id))
        except Exception as exc:
            logger.error("SVG export error for job %s: %s", job_id, exc)
            return Response(
                {"error": "SVG export failed", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 5a. SVG validation — runs all checks before touching the filesystem
        svg_errors = validate_svg(svg_string, coords)
        if svg_errors:
            logger.warning("SVG validation failed for job %s: %s", job_id, svg_errors)
            job.input_json = params.model_dump()
            job.validation_status = "invalid"
            job.warnings = svg_errors
            job.save(update_fields=["input_json", "validation_status", "warnings"])
            return Response(
                {"error": "SVG validation failed", "details": svg_errors},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # 5b. Persist SVG only after validation passes
        try:
            write_svg(svg_string, str(job_id))
        except Exception as exc:
            logger.error("SVG write error for job %s: %s", job_id, exc)
            return Response(
                {"error": "SVG write failed", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        svg_path = f"/exports/{job_id}.svg"

        # 5c. Illustrator-compatible AI generation
        try:
            ai_disk_path = export_ai(svg_string, str(job_id))
        except Exception as exc:
            logger.error("AI export error for job %s: %s", job_id, exc)
            return Response(
                {"error": "AI export failed", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not validate_ai(ai_disk_path):
            logger.error("AI validation failed for job %s: %s", job_id, ai_disk_path)
            return Response(
                {"error": "AI validation failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        ai_path = f"/exports/{job_id}.ai"

        # 6. Update DielineJob
        job.input_json = params.model_dump()
        job.validation_status = "valid"
        job.svg_output_path = svg_path
        job.ai_output_path = ai_path
        job.save(update_fields=[
            "input_json", "validation_status", "svg_output_path", "ai_output_path",
        ])

        # 7. Response
        return Response(
            build_generate_success_payload(
                job_id=str(job_id),
                svg_path=svg_path,
                ai_path=ai_path,
                coords=coords,
                warnings=list(job.warnings) if job.warnings else [],
            ),
            status=status.HTTP_200_OK,
        )


class SaveProductView(LoginRequiredMixin, APIView):
    """
    POST /api/dielines/{job_id}/save-product/

    Scenario B only. Creates a Product from the confirmed dimensions stored in
    DielineJob.input_json and links it back to the job.
    """

    def post(self, request, job_id):
        # 1. Load DielineJob
        try:
            job = DielineJob.objects.get(pk=job_id)
        except DielineJob.DoesNotExist:
            raise Http404(f"DielineJob {job_id} not found")

        # 2. Scenario guard
        if job.scenario != "B":
            return Response(
                {"error": "save-product is only available for Scenario B jobs"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Pull confirmed dimensions from input_json
        input_json = job.input_json or {}
        dims = input_json.get("dimensions", {})
        width_mm  = dims.get("width_mm")
        depth_mm  = dims.get("depth_mm")
        height_mm = dims.get("height_mm")

        if not all([width_mm, depth_mm, height_mm]):
            return Response(
                {"error": "DielineJob.input_json is missing dimension data. "
                          "Run /generate/ before saving a product."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product_name = request.data.get("product_name", "")
        product_type = request.data.get("product_type", "")
        notes        = request.data.get("notes", "")

        if not product_name:
            return Response(
                {"error": "product_name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Create Product
        Product = apps.get_model("core", "Product")
        product = Product.objects.create(
            name=product_name,
            product_type=product_type,
            width_mm=width_mm,
            depth_mm=depth_mm,
            height_mm=height_mm,
            notes=notes,
        )

        # 5 & 6. Link job → product and save
        job.product = product
        job.save(update_fields=["product"])

        # 7. Response
        return Response(
            {
                "status": "success",
                "product_id": product.pk,
                "message": "Product saved to library.",
            },
            status=status.HTTP_201_CREATED,
        )


class InspirationView(LoginRequiredMixin, APIView):
    """
    GET /api/dielines/inspiration/?product_type=eyeliner

    Returns up to 5 completed DielineJobs for reference in the dashboard.
    """

    def get(self, request):
        qs = (
            DielineJob.objects
            .filter(validation_status="valid")
            .exclude(svg_output_path="")
            .select_related("product")
            .order_by("-created_at")
        )

        product_type = request.query_params.get("product_type", "").strip()
        if product_type:
            qs = qs.filter(product__product_type=product_type)

        results = []
        for job in qs[:_INSPIRATION_LIMIT]:
            input_json = job.input_json or {}
            dims = input_json.get("dimensions", {})
            product = job.product

            results.append({
                "job_id":        str(job.pk),
                "product_name":  product.name if product else "",
                "product_type":  product.product_type if product else "",
                "flat_width_mm": dims.get("width_mm"),
                "flat_height_mm": dims.get("height_mm"),
                "created_at":    job.created_at.isoformat(),
            })

        return Response({"results": results}, status=status.HTTP_200_OK)
