# Repository Guidelines

## Project Structure & Module Organization

This is a Python/Django repository for generating print-ready straight tuck end carton dielines. Core source lives under `apps/`: `apps/dielines/geometry/` calculates coordinates, `apps/dielines/exporters/` writes and validates SVG output, `apps/dielines/validators/` defines Pydantic input contracts, and `apps/dielines/api/` exposes DRF views. Agent-oriented extraction logic lives in `apps/pipeline/agents/`. Tests are in `apps/dielines/tests/`, documentation and design decisions are in `docs/`, and generated SVG examples belong in `exports/`.

## Build, Test, and Development Commands

- `python -m venv .venv` creates a local virtual environment.
- `.venv/bin/pip install -r requirements.txt` installs Django, DRF, Pydantic, Shapely, svgwrite, Anthropic, and pytest.
- `.venv/bin/python -m pytest` runs the full test suite.
- `.venv/bin/python -m pytest apps/dielines/tests/test_svg_validator.py` runs a focused test file while iterating.

No `manage.py`, `pyproject.toml`, or project-level formatter configuration is present in this checkout; add those deliberately before documenting new commands.

## Coding Style & Naming Conventions

Use Python 3.11+ style with 4-space indentation, type hints, and `from __future__ import annotations` in new modules when forward references are useful. Keep geometry functions deterministic and unit-aware; names should include units where ambiguity is possible, for example `width_mm`, `safe_margin_mm`, or `flat_height_mm`. Preserve existing SVG layer IDs and print colors unless a documented geometry decision changes them.

## Testing Guidelines

Use pytest and name files `test_*.py`. Prefer invariant-based assertions for geometry instead of brittle exact coordinate checks, matching the current tests. SVG changes should cover structure, layer IDs, well-formed XML, validator behavior, and representative product dimensions. Run the full suite before handing off; if failures are unrelated, record the failing tests and the observed error.

## Commit & Pull Request Guidelines

This working tree does not include Git metadata, so no historical commit convention can be inferred. Use short, imperative commit subjects such as `Fix tuck flap guard calculation` or `Add SVG validator coverage`. Pull requests should include a concise summary, linked issue or task, test commands run, and sample SVGs or screenshots when export geometry changes.

## Security & Configuration Tips

Do not commit `.venv/`, `__pycache__/`, `.pytest_cache/`, `.DS_Store`, or private API keys. Anthropic-backed agent code should read credentials from the environment, not hard-coded settings. Treat files in `exports/` as generated artifacts unless they are intentional fixtures.
