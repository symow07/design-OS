"""Image Producer visual grounding.

2026-07-07 wired the reference library into images.edit. Phase 2B-3V then
corrected the authorization boundary: the product-matched HOUSE INDEX
(DesignReference / select_references) must NEVER reach the provider as an image
file — only task-scoped, human-approved concept references and task uploads
may. These tests pin the corrected behaviour: a bare house reference no longer
grounds via edit; an APPROVED concept reference does; with nothing
attachable at all (or on dall-e models) the plain generate path stays.

§BH57(a)3 separated two states these tests had been treating as one. "No
authorised reference" used to imply "nothing attached", because a lone brand
logo was dropped too. The logo is now attached on its own — the prompt had
been claiming it either way — so the boundary is still that zero house
references reach the provider, but it is no longer proved by counting provider
calls. It is proved by naming the files that were attached.
"""
from __future__ import annotations

import base64
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.core.models import Brand, DesignReference, Product
from apps.pipeline.agents.image_producer import ImageProducerAgent
from apps.pipeline.models import DesignTask, GeneratedImage

_PROMPTS = [{
    'direction_name': 'Silk Column',
    'full_prompt': 'a tall carton with an oversized serif SILK VEIL wordmark',
    'notes': '',
}]


def _b64_response():
    data = MagicMock()
    data.url = None
    data.b64_json = base64.b64encode(b'fake png bytes').decode()
    resp = MagicMock()
    resp.data = [data]
    return resp


class ImageProducerGroundingTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        self.brand = Brand.objects.create(name='BBROSE', master_brief='x')
        self.product = Product.objects.create(
            brand=self.brand, product_id='CO-9', name='Silk Veil Lip Gloss',
            category='CO', year=2026, product_type='lip gloss',
        )
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product,
            task_text='lip gloss carton', status='running',
        )
        self.logo = Path(self.media) / 'logo.png'
        self.logo.write_bytes(b'\x89PNG logo')

    def _add_reference(self):
        png = Path(self.media) / 'ref1.png'
        png.write_bytes(b'\x89PNG ref')
        DesignReference.objects.create(
            name='ref1', image_path='ref1.png', category='CO',
            product_type='lip gloss', tags=['gloss'], summary='lip gloss ref',
        )

    def _approve_concept_reference(self):
        """Approve a task-scoped concept reference with a real file (the only
        authorised design-reference channel after 2B-3V)."""
        from apps.pipeline.models import (
            ConceptInfluencePlan, ConceptReference)
        png = Path(self.media) / 'concept.png'
        png.write_bytes(b'\x89PNG concept')
        row = ConceptReference.objects.create(
            task=self.task, source_type='HISTORICAL_DESIGN_REFERENCE',
            library_item_id='design_reference:1', title='approved ref',
            image_root='media', image_path='concept.png',
            permission_status=ConceptReference.PERMISSION_APPROVED)
        ConceptInfluencePlan.objects.create(
            task=self.task, schema_version='material_influence_plan/1.0',
            plan={'references': [{'reference_id': row.pk}]}, plan_hash='h' * 8)
        return row

    @patch('apps.pipeline.agents.image_producer.openai.images.generate')
    @patch('apps.pipeline.agents.image_producer.openai.images.edit')
    def test_house_reference_no_longer_grounds_via_edit(self, mock_edit, mock_gen):
        """A bare product-matched house DesignReference is NOT an authorised visual input — it must not
        reach images.edit (the 2B-3V fix). THE BOUNDARY IS UNCHANGED; the proof of it is stronger.

        Until §BH57(a)3 this asserted `mock_edit.assert_not_called()`, which was true for a reason that
        was about to stop being true: a lone brand logo was dropped as well, so "nothing authorised" and
        "nothing attached" were one state. Attaching the logo separates them. Counting provider calls
        could never have told a house reference from a brand mark anyway — so the file is named.
        """
        self._add_reference()
        mock_edit.return_value = _b64_response()
        with override_settings(MEDIA_ROOT=self.media, IMAGE_MODEL='gpt-image-1',
                               BRAND_LOGO_PATH=str(self.logo)):
            ImageProducerAgent(self.task, _PROMPTS).run()
        mock_gen.assert_not_called()
        mock_edit.assert_called_once()
        attached = [fh.name for fh in mock_edit.call_args.kwargs['image']]
        self.assertEqual(attached, [str(self.logo)],
                         'the brand mark, and nothing the house index matched')
        self.assertNotIn('ref1.png', ' '.join(attached))

    @patch('apps.pipeline.agents.image_producer.openai.images.generate')
    @patch('apps.pipeline.agents.image_producer.openai.images.edit')
    def test_bh71_a_concept_that_nearly_copies_a_used_trend_picture_is_flagged_as_it_is_drawn(self, mock_edit, mock_gen):
        """§BH71 PART 2 "never near-copied": every concept the producer draws is compared, as it is saved, with the
        trend pictures its directions used — flagged beside it when close, never removed."""
        import io
        import random

        from PIL import Image

        from apps.pipeline.models import TrendBoard, TrendPick, WebResearchSession, WebSourceRecord
        picture = io.BytesIO()
        Image.frombytes("RGB", (64, 48), random.Random(5).randbytes(64 * 48 * 3)).save(picture, "PNG")
        png = picture.getvalue()
        kept = Path(self.media) / "trend_1.png"
        kept.write_bytes(png)
        session = WebResearchSession.objects.create(product_identity="trend board", modes=["TREND_BOARD"])
        source = WebSourceRecord.objects.create(session=session, original_url="https://cdn.dribbble.com/1.png",
                                                classification="image", quarantine_path=str(kept))
        board = TrendBoard.objects.create(task=self.task, status=TrendBoard.CONFIRMED, confirmed_how="his click")
        pick = TrendPick.objects.create(board=board, number=1, kind=TrendPick.PICTURE, platform="dribbble",
                                        page_url="https://dribbble.com/shots/1", image_url=source.original_url,
                                        source=source, sha256="a" * 64, used=True)
        board.used_at_confirm = [pick.pk]
        board.save()
        data = MagicMock()
        data.url = None
        data.b64_json = base64.b64encode(png).decode()
        answer = MagicMock()
        answer.data = [data]
        mock_edit.return_value = answer
        mock_gen.return_value = answer
        with override_settings(MEDIA_ROOT=self.media, IMAGE_MODEL='gpt-image-1', BRAND_LOGO_PATH=str(self.logo)):
            images = ImageProducerAgent(self.task, _PROMPTS).run()
        near = GeneratedImage.objects.get(pk=images[0].pk).reference_provenance["trend_near_copy"]
        self.assertEqual(near["close_to"], [{"number": 1, "platform": "Dribbble", "bits_apart": 0}])
        self.assertEqual(GeneratedImage.objects.filter(task=self.task).count(), 1)     # nothing removed

    @patch('apps.pipeline.agents.image_producer.openai.images.generate')
    @patch('apps.pipeline.agents.image_producer.openai.images.edit')
    def test_approved_concept_reference_grounds_via_edit(self, mock_edit, mock_gen):
        self._approve_concept_reference()
        mock_edit.return_value = _b64_response()
        with override_settings(MEDIA_ROOT=self.media, IMAGE_MODEL='gpt-image-1',
                               BRAND_LOGO_PATH=str(self.logo)):
            images = ImageProducerAgent(self.task, _PROMPTS).run()

        mock_gen.assert_not_called()
        mock_edit.assert_called_once()
        kwargs = mock_edit.call_args.kwargs
        assert len(kwargs['image']) == 2          # logo + 1 approved concept ref
        assert 'STYLE GROUNDING' in kwargs['prompt']
        assert 'official BBROSE logo' in kwargs['prompt']
        assert _PROMPTS[0]['full_prompt'] in kwargs['prompt']
        # stored prompt stays the raw brief so reruns don't double-wrap
        assert images[0].prompt_used == _PROMPTS[0]['full_prompt']
        assert images[0].image_file  # b64 bytes were saved
        assert images[0].reference_provenance['concept_reference_ids']

    @patch('apps.pipeline.agents.image_producer.openai.images.generate')
    @patch('apps.pipeline.agents.image_producer.openai.images.edit')
    def test_a_lone_logo_is_attached_and_the_prompt_tells_the_truth_about_it(self, mock_edit, mock_gen):
        """§BH57(a)3 REPLACES `test_no_references_falls_back_to_generate`, which asserted
        `mock_edit.assert_not_called()` here — the old rule, "no references -> plain generate", under which a lone
        logo never reached the model.

        §BH56 measured what that cost: task 84 ran with zero references, so no logo was attached, while the prompt
        the system had instructed said "the official BBROSE logo placed <where>". Provenance:
        `official_logo_included: false`. The model was told a logo was attached, none was, and it drew the
        wordmark itself — badly. The owner: "Attach it … a lie to the model is worse than a limit."

        And the grounding must not swap one lie for another: with only the logo attached there IS no reference
        design, so the preamble may not say "the attached images are real BBROSE production packaging designs".
        """
        mock_edit.return_value = _b64_response()
        with override_settings(MEDIA_ROOT=self.media, IMAGE_MODEL='gpt-image-1',
                               BRAND_LOGO_PATH=str(self.logo)):
            images = ImageProducerAgent(self.task, _PROMPTS).run()
        mock_gen.assert_not_called()
        mock_edit.assert_called_once()
        kwargs = mock_edit.call_args.kwargs
        assert len(kwargs['image']) == 1, 'the logo alone, and nothing pretending to be a reference'
        assert 'official BBROSE logo' in kwargs['prompt']
        assert 'ONE attached image is the official BBROSE brand mark' in kwargs['prompt']
        assert 'real BBROSE production packaging designs' not in kwargs['prompt']
        assert images[0].reference_provenance['official_logo_included'] is True
        assert GeneratedImage.objects.filter(task=self.task).count() == 1

    @patch('apps.pipeline.agents.image_producer.openai.images.generate')
    @patch('apps.pipeline.agents.image_producer.openai.images.edit')
    def test_with_neither_logo_nor_references_the_plain_generate_path_is_unchanged(self, mock_edit, mock_gen):
        """The half of the old contract that survives: nothing to attach, so nothing is attached."""
        mock_gen.return_value = _b64_response()
        with override_settings(MEDIA_ROOT=self.media, IMAGE_MODEL='gpt-image-1',
                               BRAND_LOGO_PATH='/nonexistent/bh57/no-logo.png'):
            ImageProducerAgent(self.task, _PROMPTS).run()
        mock_edit.assert_not_called()
        mock_gen.assert_called_once()
        assert GeneratedImage.objects.filter(task=self.task).count() == 1

    @patch('apps.pipeline.agents.image_producer.openai.images.generate')
    @patch('apps.pipeline.agents.image_producer.openai.images.edit')
    def test_dalle_models_never_use_edit(self, mock_edit, mock_gen):
        self._add_reference()
        mock_gen.return_value = _b64_response()
        with override_settings(MEDIA_ROOT=self.media, IMAGE_MODEL='dall-e-3',
                               BRAND_LOGO_PATH=str(self.logo)):
            ImageProducerAgent(self.task, _PROMPTS).run()
        mock_edit.assert_not_called()
        mock_gen.assert_called_once()
