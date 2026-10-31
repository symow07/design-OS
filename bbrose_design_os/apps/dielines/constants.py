"""Shared dieline print/construction defaults (Milestone 10.1, audit H4).

Single source of truth for the optional generation parameters so the agent
path (apps.pipeline.agents.dieline_agent) and the API path
(apps.dielines.api.views) can never drift apart. [The API path's generate door
was removed in the clean-up of 2026-10-04; the agent path is the one reader.] The values match the seeded
DielineTemplate row and the pydantic schema defaults in
apps.dielines.validators.schema (_PrintSettings / _Construction).
"""
from __future__ import annotations

DEFAULT_BLEED_MM = 3.0
DEFAULT_SAFE_MARGIN_MM = 4.0
DEFAULT_GLUE_TAB_MM = 10.0
DEFAULT_BOARD_THICKNESS_MM = 0.35

# Deliverable kinds servable via /api/dielines/jobs/<id>/files/<kind>.
FILE_KINDS = ("svg", "ai", "pdf", "spec")
