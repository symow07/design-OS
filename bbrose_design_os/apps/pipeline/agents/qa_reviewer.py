from apps.pipeline.services.cost_ledger import BudgetExceededError as _RescueBudgetError
import json

from django.conf import settings

from apps.pipeline.services.claude_service import (
    call_claude, extract_json, image_block_from_file,
)
from apps.pipeline.services.brand_context import build_brand_context, get_brand_hexes
from apps.pipeline.services.image_checks import run_image_checks

from apps.pipeline.services.concept_quality import (
    evaluate, image_sha256,
)

QA_REVIEWER_SYSTEM = """
You are an independent senior beauty-product and retail-display art director.
Judge the supplied image against the actual brief, not the generator's claims.
The brief's colours, mood, form, dimensions, languages and copy take precedence.
Clear glass and chrome are materials, not inks. White, silver, cool, dark and
monochrome directions are allowed when deliberate and legible. Restraint is
allowed; no generic roses, arches or all-panel wallpaper unless briefed.
Assess every dimension separately: colour_contrast, focal_hierarchy,
negative_space, pattern_support, typography, shelf_impact, premium_cues,
distinctiveness, trend_relevance, beauty. 5=competent but generic, 7=credible
professional direction, 8=strong client presentation. Shelf impact is a visual
estimate, never claim a physical test. Trend relevance needs dated evidence;
do not invent virality. Garbled/missing required text is a defect, not excused.
Hard failures include wrong product/cap/count, missing required language/copy,
flattened transparent glass, unauthorized references and incorrect object type.
Do not confuse creative merit with print preflight or supplier approval.
Return JSON only:
{"observations":"what is visibly present", "hard_failures":[],
 "dimensions": {"colour_contrast":{"score":8,"observation":"specific evidence",
 "location":"specific image region","repair":"specific edit when score below8"},
 ...every one of the ten named dimensions...}}
Never emit an overall pass: the application computes it from your evidence.
"""



class QAReviewerAgent:
    """Reviews each generated concept render with Claude vision, blended with
    deterministic, model-free checks (palette distance + aspect) that cannot
    drift. OCR is informational only — it never fails a concept render.

    Returns a list of per-image review dicts (the ``reviews[]`` contract the
    dashboard and the ARIA revision loop consume): each has ``image_id``,
    ``passed``, ``score``, ``issues``, ``recommendation`` plus ``observations``
    and a ``deterministic`` block.
    """

    def __init__(self, images, brand_id, log_fn=None, product_profile=None):
        self.images = images
        self.brand_id = brand_id
        self.product_profile = product_profile or {}
        self.log = log_fn or (lambda msg, data=None, level='info': None)
        self.vision_enabled = bool(settings.ANTHROPIC_API_KEY)

    def run(self):
        self.log("Art director: reviewing each concept against the ten-part quality bar")
        if not self.vision_enabled:
            self.log(
                "Art director unavailable — concepts remain review pending",
                level='warning',
            )

        brand_context = build_brand_context(self.brand_id)
        # §BH39(e): the layer's roles are what the post-hoc check measures
        # against — brand_gov FIRST through colour_roles (Warm Gold included);
        # the seeded palettes still reach the prompt through build_brand_context.
        from apps.ire.colour_roles import brand_hexes_for_check
        brand_hexes = brand_hexes_for_check(self.brand_id) or get_brand_hexes(self.brand_id)

        colours = self.product_profile.get('preferred_colors') or []
        if isinstance(colours, str):
            colours = [colours]
        import re
        self.palette_source = 'brief' if colours else 'house guidance'
        # Named colours/materials are still sent verbatim to vision. They must
        # never silently become a canonical-palette veto.
        if colours:
            brand_hexes = [c for c in colours if isinstance(c, str) and
                           re.fullmatch(r'#[0-9a-fA-F]{6}', c.strip())]
            self.palette_source = 'brief hexes' if len(brand_hexes) == len(colours) else 'brief names/materials'
            if len(brand_hexes) != len(colours):
                brand_hexes = []
        reviews = []
        for img in self.images:
            review = self._review_one(img, brand_context, brand_hexes)
            img.qa_passed = review['passed']
            img.qa_notes = json.dumps(review)
            img.save(update_fields=['qa_passed', 'qa_notes'])
            reviews.append(review)

        passed = sum(1 for r in reviews if r['passed'])
        self.log(f"QA Reviewer: {passed}/{len(reviews)} images passed")
        return reviews

    # --- per-image pipeline ------------------------------------------------

    def _review_one(self, img, brand_context, brand_hexes):
        path = self._image_path(img)
        digest = image_sha256(img)
        vision = self._vision_review(img, path, brand_context)
        review = evaluate(vision if digest and image_sha256(img) == digest else None)
        review.update(image_id=img.id, direction_name=img.direction_name,
                      image_sha256=digest,
                      palette_source=getattr(self, 'palette_source', 'house guidance'))
        try:
            checks = run_image_checks(path, brand_hexes) if path else None
        except Exception as exc:
            if isinstance(exc, _RescueBudgetError):
                raise
            checks = {'unavailable': str(exc)}
        review['deterministic'] = checks or {}
        self._apply_deterministic(review, checks, vision_available=vision is not None)
        return review

    def _vision_review(self, img, path, brand_context):
        """Call Claude with the actual image attached. Returns the parsed review
        dict, or None if vision is disabled / the call or parse fails."""
        if not self.vision_enabled:
            return None

        # Milestone 8.6: if the local image file is missing (failed download),
        # skip the vision review explicitly instead of silently degrading to a
        # text-only judgement of pixels Claude never saw.
        if not path:
            self.log(
                f"QA Reviewer: image {img.id} has no local file — skipping "
                f"vision review; review remains pending",
                level='warning',
            )
            return None

        meta = {'direction_name': img.direction_name, 'variation_number': img.variation_number}
        # The critic sees requirements, not the generator's persuasive prompt.
        task = getattr(img, 'task', None)
        meta['brief'] = getattr(task, 'task_text', '')
        meta['reference_provenance'] = getattr(img, 'reference_provenance', {}) or {}
        from apps.pipeline.services.trend_board import board_of
        board = board_of(task) if task and getattr(task, 'pk', None) else None
        meta['dated_trend_evidence'] = getattr(board, 'brief', None) or 'Unavailable — do not claim current popularity.'
        from apps.pipeline.services.product_profile import profile_text
        product_block = profile_text(self.product_profile)
        profile_section = (
            f"\n## Product specification (form and materials must match)\n"
            f"{product_block}\n" if product_block else ""
        )
        # [his test day finding 2, 2026-09-29, design 117: concepts 1 and 2 of his Playful Drip scored 4 and 5 under the
        # pass line, first for a hot pink "not in any BBROSE canonical colour system" — the colour his brief asked for.
        # This check was never shown the brief's colours; his ruling of finding 1 ("my brief's colours win, with
        # BBROSE's logo and one house accent") reached the planner and not here. The brief's colours are shown to it]
        requested_colours = self.product_profile.get("preferred_colors") or []
        if isinstance(requested_colours, str):
            requested_colours = [requested_colours]
        colours = [str(c).strip() for c in requested_colours if str(c).strip()]
        colour_section = (
            "\n## The brief's colours — they win (the owner's ruling)\n" + "; ".join(colours) + "\n"
            "Judge the palette against these, with the BBROSE logo and at most one house accent beside them.\n"
            if colours else "")
        # [his answer 4 of 2026-10-02 (6badb27): "the concept check's mood follows the brief"] the brief's own mood
        mood = str(self.product_profile.get("mood") or "").strip()
        mood_section = ("\n## The brief's mood — judge the register against it (the owner's ruling)\n" + mood + "\n"
                        if mood else "")
        text = f"""## Brand Standards
{brand_context}
{profile_section}{colour_section}{mood_section}
## This Image (concept render)
{json.dumps(meta, indent=2)}

Review THIS image as a concept render. Respond with the JSON object only.
"""

        try:
            content = [
                {"type": "text", "text": text},
                image_block_from_file(path),
            ]
        except Exception as e:  # noqa: BLE001 — unreadable file → skip vision
            if isinstance(e, _RescueBudgetError):
                raise
            self.log(
                f"QA Reviewer: could not attach image {img.id} ({e}) — "
                f"skipping vision review",
                level='warning',
            )
            return None

        try:
            from django.conf import settings as dj_settings
            response = call_claude(
                QA_REVIEWER_SYSTEM, content, max_tokens=2800,
                operation="qa_vision_review",
                model=(dj_settings.QA_VISION_MODEL or dj_settings.CLAUDE_MODEL_FAST),
            )
            return extract_json(response)
        except Exception as e:  # noqa: BLE001 — degrade to deterministic-only
            if isinstance(e, _RescueBudgetError):
                raise
            self.log(
                f"QA Reviewer: vision review failed for image {img.id} — {e}",
                level='error',
            )
            return None

    def _apply_deterministic(self, review, checks, vision_available):
        """Image diagnostics are evidence, never an aesthetic pass or palette veto.

        Canvas aspect is not product geometry; glass, lighting and the background
        are not ink. Hard physical/copy failures are adjudicated separately.
        """
        if not checks:
            return
        review['deterministic_role'] = 'informational; does not replace the critic'
        if (checks.get('palette') or {}).get('on_brand') is False:
            review.setdefault('notes', []).append(
                'Palette diagnostic differs from the resolved guidance; inspect materials and lighting.')
        if (checks.get('aspect') or {}).get('ok') is False:
            review.setdefault('notes', []).append('Canvas aspect differs from the configured image format.')

    # --- helpers -----------------------------------------------------------

    def _image_path(self, img):
        """Local filesystem path to the saved render, or None if unavailable.

        Uses the saved file (not ``image_url`` — DALL·E URLs expire) so vision
        and the colour checks operate on the real pixels.
        """
        try:
            if img.image_file and img.image_file.storage.exists(img.image_file.name):
                return img.image_file.path
        except Exception as rescue_error:  # noqa: BLE001 — remote/missing storage → no local path
            if isinstance(rescue_error, _RescueBudgetError):
                raise
            pass
        return None


def _as_int(value, default=0):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default
