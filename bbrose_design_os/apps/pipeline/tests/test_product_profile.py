"""Product identification step (2026-07-07).

The Amber Hour run generated tall skincare-style cartons (with a dropper
bottle prop) for an eyeshadow palette because no stage knew what product the
task was about. These tests pin the resolve-once, thread-everywhere design.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.core.models import Brand, Product
from apps.pipeline.models import DesignTask
from apps.pipeline.services.product_profile import (
    profile_text,
    resolve_product_profile,
)


def _claude_response(json_data):
    block = MagicMock()
    block.type = 'text'
    block.text = json.dumps(json_data)
    resp = MagicMock()
    resp.content = [block]
    return resp


class ResolveProductProfileTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name='BBROSE', master_brief='x')

    def _task(self, text, product=None):
        return DesignTask.objects.create(
            brand=self.brand, task_text=text, status='queued', product=product,
        )

    def test_product_record_wins_without_any_model_call(self):
        # [his answer 4 of 2026-10-02 (6badb27): a design started from a product record reads its brief's constraints by
        # the one extraction call a brief-only design makes, where inference is on — it is off here, as under every
        # test, so the record still answers without a call; the call is pinned by the test after the next]
        product = Product.objects.create(
            brand=self.brand, product_id='CO-31', name='Amber Hour Palette',
            category='CO', year=2026, product_type='eyeshadow palette',
        )
        profile = resolve_product_profile(self._task('palette carton', product))
        assert profile['source'] == 'record'
        assert profile['category'] == 'CO'
        assert profile['product_type'] == 'eyeshadow palette'

    def test_inference_disabled_returns_empty(self):
        # settings.py forces PRODUCT_INFERENCE=False under pytest
        assert resolve_product_profile(self._task('eyeshadow palette box')) == {}

    @override_settings(PRODUCT_INFERENCE=True, ANTHROPIC_API_KEY='k')
    @patch('apps.pipeline.services.claude_service.call_claude')
    def test_inferred_profile_from_task_text(self, mock_claude):
        mock_claude.return_value = _claude_response({
            'name': 'Amber Hour Eyeshadow Palette',
            'category': 'CO',
            'product_type': 'eyeshadow palette',
            'physical_format': 'wide, low-profile landscape carton (flat palette inside)',
        })
        profile = resolve_product_profile(self._task('amber hour palette carton'))
        assert profile['source'] == 'inferred'
        assert profile['category'] == 'CO'
        # 2A-6D-CORR-2: an inferred form is a guess, not a fact — it lives in
        # the quarantined diagnostic field, never in physical_format.
        assert profile['physical_format'] == ''
        assert profile['structural_provenance'] == 'INFERRED_NONAUTHORITATIVE'
        assert 'landscape carton' in profile['inferred_non_authoritative_context']
        assert mock_claude.call_args.kwargs['operation'] == 'product_identification'

    @override_settings(PRODUCT_INFERENCE=True, ANTHROPIC_API_KEY='k')
    @patch('apps.pipeline.services.claude_service.call_claude')
    def test_model_failure_degrades_to_empty(self, mock_claude):
        mock_claude.side_effect = RuntimeError('api down')
        assert resolve_product_profile(self._task('mystery box')) == {}

    def test_profile_text_rendering(self):
        # 2A-6D-CORR-2: only authoritative structure renders as a carton
        # form; an inferred one renders the explicit UNKNOWN block instead.
        text = profile_text({
            'name': 'Amber Hour', 'category': 'CO',
            'product_type': 'eyeshadow palette',
            'physical_format': 'wide landscape carton', 'source': 'inferred',
        })
        assert 'Type: eyeshadow palette' in text
        assert 'wide landscape carton' not in text
        assert 'STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED' in text
        verified = profile_text({
            'name': 'Amber Hour', 'category': 'CO',
            'physical_format': 'wide landscape carton', 'source': 'record',
            'structural_provenance': 'VERIFIED_PRODUCT_RECORD',
        })
        assert 'Carton form: wide landscape carton' in verified
        assert profile_text({}) == ''

    @override_settings(PRODUCT_INFERENCE=True, ANTHROPIC_API_KEY='k')
    @patch('apps.pipeline.services.claude_service.call_claude')
    def test_his_answer_a_record_design_reads_the_briefs_colours_and_copy(self, mock_claude):
        """His answer 4 of 2026-10-02 (transcribed at 6badb27): "designs started from a product record read the brief's
        colours and copy". The record still names the product, its type and its form; the brief's own constraint lists —
        its required copy, the colours it prefers and forbids — are read beside it, by the one extraction call a brief-only
        design makes; a list the brief leaves empty is not added."""
        mock_claude.return_value = _claude_response({
            'name': 'Some Other Name', 'category': 'SK', 'product_type': 'serum', 'physical_format': '',
            'required_copy': ['Body Lotion / لوشن للجسم'], 'preferred_colors': ['hot pink', 'soft pink', 'gold'],
            'prohibited_colors': ['black'], 'prohibited_motifs': [], 'production_constraints': []})
        product = Product.objects.create(
            brand=self.brand, product_id='CO-32', name='Amber Hour Palette',
            category='CO', year=2026, product_type='eyeshadow palette',
        )
        profile = resolve_product_profile(self._task('an eyeshadow palette in hot pink, soft pink and gold', product))
        assert (profile['source'], profile['name'], profile['product_type']) == (
            'record', 'Amber Hour Palette', 'eyeshadow palette')            # the record still names the product
        assert profile['preferred_colors'] == ['hot pink', 'soft pink', 'gold']
        assert profile['prohibited_colors'] == ['black'] and profile['required_copy'] == ['Body Lotion / لوشن للجسم']
        assert 'prohibited_motifs' not in profile and mock_claude.call_count == 1


    def test_his_answer_the_concept_checks_mood_follows_the_brief(self):
        """His answer 4 of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6badb27): "the concept check's mood
        follows the brief". The brief's own "Mood:" paragraph is read from its words into the profile; the concept check is
        told it under its own heading and judges the register against it, never marking a concept down for not being soft
        luxury; a brief with no mood reads as before, and the check keeps the house's register."""
        from apps.pipeline.agents.qa_reviewer import QA_REVIEWER_SYSTEM
        from apps.pipeline.services.product_profile import brief_mood
        brief = ("Coconut Rose Body Lotion\n\nMood: playful, retro, sweet —\n  a candy-shop drip, loud and happy.\n\n"
                 "Colours: hot pink, soft pink")
        assert brief_mood(brief) == "playful, retro, sweet — a candy-shop drip, loud and happy."
        assert brief_mood("a calm serum, no mood line") == ""
        assert "colours, mood, form" in QA_REVIEWER_SYSTEM and "Restraint is" in QA_REVIEWER_SYSTEM
        product = Product.objects.create(brand=self.brand, product_id='SK-117', name='Coconut Rose Body Lotion',
                                         category='SK', year=2026, product_type='body lotion')
        profile = resolve_product_profile(self._task(brief, product))
        assert profile['source'] == 'record' and profile['mood'] == brief_mood(brief), profile

class ProfileThreadingTests(TestCase):
    """The profile must actually shape reference selection and prompts."""

    def setUp(self):
        self.brand = Brand.objects.create(name='BBROSE', master_brief='x')
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text='golden hour carton', status='queued',
        )

    def test_profile_gives_category_bonus_in_reference_selection(self):
        import shutil
        import tempfile
        from pathlib import Path
        from apps.core.models import DesignReference
        from apps.pipeline.services.reference_index import select_references

        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        for name, cat, ptype in (
            ('pal1', 'CO', 'eyeshadow palette'), ('ser1', 'SK', 'serum carton'),
        ):
            (Path(media) / f'{name}.png').write_bytes(b'\x89PNG')
            DesignReference.objects.create(
                name=name, image_path=f'{name}.png', category=cat,
                product_type=ptype, tags=[], summary=ptype,
            )
        profile = {'category': 'CO', 'product_type': 'eyeshadow palette'}
        with self.settings(MEDIA_ROOT=media):
            picked = select_references(self.task, 1, profile=profile)
        assert picked and picked[0].endswith('pal1.png')

    @patch('apps.pipeline.agents.prompt_engineer.call_claude')
    def test_his_answer_the_briefs_colours_reach_the_step_that_makes_the_concept_picture(self, mock_claude):
        """His answer 1 of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6badb27): "the brief's colours go into
        the step that MAKES the concept picture, not only the drawing." The step that writes each concept picture's
        prompt is told the brief's colours and the colours it forbids as dominant, under his ruling's own heading (the
        brief's colours win, the BBROSE logo and at most one house accent beside them); a brief that names no colours
        leaves the prompt exactly as it was."""
        from apps.pipeline.agents.prompt_engineer import PromptEngineerAgent
        from apps.pipeline.services.product_profile import BRIEF_COLOURS_HEADING, brief_colours_text, with_brief_colours
        mock_claude.return_value = _claude_response({'prompts': []})
        profile = {'name': 'Coconut Rose Body Lotion', 'category': 'SK', 'product_type': 'body lotion',
                   'physical_format': '', 'source': 'inferred', 'structural_provenance': 'INFERRED_NONAUTHORITATIVE',
                   'preferred_colors': ['hot pink', 'soft pink', 'cream', 'gold'], 'prohibited_colors': ['black']}
        PromptEngineerAgent([{'name': 'd1'}], None, product_profile=profile).run()
        sent = mock_claude.call_args.args[1]
        assert BRIEF_COLOURS_HEADING in sent
        assert 'Colours: hot pink; soft pink; cream; gold' in sent and 'Never a dominant colour: black' in sent
        bare = dict(profile, preferred_colors=[], prohibited_colors=[])
        assert brief_colours_text(bare) == '' and with_brief_colours('block', bare) == 'block'
        PromptEngineerAgent([{'name': 'd1'}], None, product_profile=bare).run()
        assert BRIEF_COLOURS_HEADING not in mock_claude.call_args.args[1]

    @patch('apps.pipeline.agents.prompt_engineer.call_claude')
    def test_prompt_engineer_receives_carton_form(self, mock_claude):
        from apps.pipeline.agents.prompt_engineer import PromptEngineerAgent
        mock_claude.return_value = _claude_response({'prompts': []})
        PromptEngineerAgent(
            [{'name': 'd1'}], None,
            product_profile={'name': 'Amber Hour', 'category': 'CO',
                             'product_type': 'eyeshadow palette',
                             'physical_format': 'wide landscape carton',
                             'source': 'record',
                             'structural_provenance': 'VERIFIED_PRODUCT_RECORD'},
        ).run()
        sent = mock_claude.call_args.args[1]
        assert 'Carton form: wide landscape carton' in sent

    @patch('apps.pipeline.agents.prompt_engineer.call_claude')
    def test_prompt_engineer_never_receives_an_inferred_form(self, mock_claude):
        from apps.pipeline.agents.prompt_engineer import PromptEngineerAgent
        mock_claude.return_value = _claude_response({'prompts': []})
        PromptEngineerAgent(
            [{'name': 'd1'}], None,
            product_profile={'name': 'Baked Powder', 'category': 'CO',
                             'product_type': 'face powder',
                             'physical_format': '', 'source': 'inferred',
                             'structural_provenance': 'INFERRED_NONAUTHORITATIVE',
                             'inferred_non_authoritative_context':
                                 'small upright tuck-end carton'},
        ).run()
        sent = mock_claude.call_args.args[1]
        assert 'tuck' not in sent.lower()
        assert 'STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED' in sent
