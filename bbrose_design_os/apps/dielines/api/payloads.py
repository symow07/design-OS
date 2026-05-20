from __future__ import annotations

from apps.dielines.geometry.coordinates import DielineCoordinates


def build_generate_success_payload(
    *,
    job_id: str,
    svg_path: str,
    ai_path: str,
    coords: DielineCoordinates,
    warnings: list,
) -> dict:
    return {
        "status": "success",
        "job_id": job_id,
        "svg_file": svg_path,
        "ai_file": ai_path,
        "summary": {
            "flat_width_mm": coords.flat_width_mm,
            "flat_height_mm": coords.flat_height_mm,
            "panel_count": len(coords.panels),
        },
        "warnings": warnings,
    }
