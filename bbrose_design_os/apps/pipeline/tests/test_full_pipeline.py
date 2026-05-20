import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from apps.core.models import Brand, ColorSystem, PackagingStructure, Product
from apps.pipeline.agents.aria import ARIAAgent
from apps.pipeline.models import (
    AgentLog,
    CreativeBrief,
    DesignTask,
    GeneratedImage,
    PackagingOutput,
)


MOCK_DIRECTIONS = [
    {
        "name": "Velvet Petal",
        "rationale": "Evolves from BBROSE's core blush philosophy",
        "palette": "CS-001 — Blush primary with Rose Gold accent",
        "material": "Glossy Acrylic",
        "finish_combination": "High-gloss + rose gold foil",
        "connected_to": "Core product line",
        "prompt_seed": "Soft luxury surface with blush gradients and rose gold detail",
    }
]

MOCK_PROMPTS = [
    {
        "direction_name": "Velvet Petal",
        "full_prompt": "flat surface artwork, blush pink cylinder wrap, #F2C4CE primary, rose gold metallic foil detail",
        "aspect_ratio": "9:21",
        "notes": "Portrait orientation for cylindrical wrap",
    }
]

MOCK_QA_RESULTS = {
    "reviews": [
        {
            "image_id": None,
            "passed": True,
            "score": 8,
            "issues": [],
            "recommendation": "approve",
        }
    ]
}


class FullPipelineTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser('test', 'test@test.com', 'password')

        self.brand = Brand.objects.create(
            name='BBROSE Test',
            master_brief='Luxury beauty brand. Blush pink. Rose gold. Soft luxury.',
            what_we_are_not='Not clinical. Not cold. Not masculine.',
        )

        self.color_system = ColorSystem.objects.create(
            brand=self.brand,
            name='Blush Core',
            system_id='CS-001',
            palette=[{'role': 'Primary', 'hex': '#F2C4CE'}],
            image_generation_context='blush pink, rose gold, warm cream',
            status='canonical',
        )

        self.structure = PackagingStructure.objects.create(
            brand=self.brand,
            name='Lip Oil Roller',
            structure_id='PKG-STR-001',
            structure_type='cylindrical tube',
            dimensions={'diameter': '11mm', 'height': '82mm'},
            printable_surface={'width': '34.6mm', 'height': '82mm'},
            surface_zones={'logo_zone': 'upper 30%'},
            status='active',
        )

        self.product = Product.objects.create(
            brand=self.brand,
            product_id='BBR-CO-001',
            name='Test Lip Oil',
            category='CO',
            year=2025,
            status='active',
            packaging_structure=self.structure,
            color_system=self.color_system,
        )

    def _make_claude_response(self, json_data):
        mock_block = MagicMock()
        mock_block.type = 'text'
        mock_block.text = json.dumps(json_data)
        mock_resp = MagicMock()
        mock_resp.content = [mock_block]
        return mock_resp

    def _make_openai_response(self):
        mock_data = MagicMock()
        mock_data.url = 'https://example.com/test_image.png'
        mock_resp = MagicMock()
        mock_resp.data = [mock_data]
        return mock_resp

    @patch('apps.pipeline.agents.image_producer.requests.get')
    @patch('apps.pipeline.agents.image_producer.openai.images.generate')
    @patch('apps.pipeline.agents.qa_reviewer.call_claude')
    @patch('apps.pipeline.agents.prompt_engineer.call_claude')
    @patch('apps.pipeline.agents.creative_director.call_claude')
    def test_full_pipeline_gate1(self, mock_cd, mock_pe, mock_qa, mock_openai_gen, mock_img_get):
        """Test pipeline runs from start to Gate 1 with all agents mocked."""

        mock_cd.return_value = self._make_claude_response({'directions': MOCK_DIRECTIONS})
        mock_pe.return_value = self._make_claude_response({'prompts': MOCK_PROMPTS})
        mock_openai_gen.return_value = self._make_openai_response()

        mock_img_response = MagicMock()
        mock_img_response.status_code = 200
        mock_img_response.content = b'fake_png_bytes'
        mock_img_get.return_value = mock_img_response

        def qa_side_effect(system, user_message, **kwargs):
            images = GeneratedImage.objects.filter(task=self.task)
            results = [
                {
                    'image_id': img.id,
                    'passed': True,
                    'score': 8,
                    'issues': [],
                    'recommendation': 'approve',
                }
                for img in images
            ]
            return self._make_claude_response({'reviews': results})

        mock_qa.side_effect = qa_side_effect

        self.task = DesignTask.objects.create(
            brand=self.brand,
            product=self.product,
            task_text='Create luxury packaging concept for Lip Oil',
            status='queued',
        )

        agent = ARIAAgent(self.task.id)
        agent.run()

        self.task.refresh_from_db()

        self.assertEqual(
            self.task.status, 'awaiting_gate_1',
            f"Expected awaiting_gate_1, got {self.task.status}",
        )

        logs = AgentLog.objects.filter(task=self.task)
        self.assertGreater(logs.count(), 0, "No agent logs created")

        brief = CreativeBrief.objects.filter(task=self.task).first()
        self.assertIsNotNone(brief, "CreativeBrief not created")
        self.assertEqual(len(brief.directions), 1)

        images = GeneratedImage.objects.filter(task=self.task)
        self.assertEqual(images.count(), 1, f"Expected 1 image, got {images.count()}")
        self.assertTrue(images.first().qa_passed, "QA should have passed")

        print("\n✓ All stage assertions passed.")
        print(f"  Logs: {logs.count()}")
        print(f"  Images: {images.count()}")
        print(f"  Status: {self.task.status}")

    @patch('apps.pipeline.agents.pacdora_agent.requests.post')
    @patch('apps.pipeline.agents.image_producer.requests.get')
    @patch('apps.pipeline.agents.image_producer.openai.images.generate')
    @patch('apps.pipeline.agents.qa_reviewer.call_claude')
    @patch('apps.pipeline.agents.prompt_engineer.call_claude')
    @patch('apps.pipeline.agents.creative_director.call_claude')
    def test_gate1_to_gate2(self, mock_cd, mock_pe, mock_qa, mock_gen, mock_get, mock_pacdora):
        """Test Gate 1 approval triggers Pacdora and reaches Gate 2."""

        mock_cd.return_value = self._make_claude_response({'directions': MOCK_DIRECTIONS})
        mock_pe.return_value = self._make_claude_response({'prompts': MOCK_PROMPTS})
        mock_gen.return_value = self._make_openai_response()
        mock_get.return_value = MagicMock(status_code=200, content=b'fake_png')

        self.task = DesignTask.objects.create(
            brand=self.brand,
            product=self.product,
            task_text='Gate 2 test task',
            status='queued',
        )

        def qa_side_effect(system, user_message, **kwargs):
            images = GeneratedImage.objects.filter(task=self.task)
            results = [
                {
                    'image_id': img.id,
                    'passed': True,
                    'score': 9,
                    'issues': [],
                    'recommendation': 'approve',
                }
                for img in images
            ]
            return self._make_claude_response({'reviews': results})

        mock_qa.side_effect = qa_side_effect

        mock_pacdora.return_value = MagicMock(
            status_code=200,
            json=lambda: {'render_url': 'https://pacdora.com/render/test'},
        )

        ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'awaiting_gate_1')

        image = GeneratedImage.objects.filter(task=self.task).first()
        ARIAAgent(self.task.id).resume_after_gate_1(image.id)
        self.task.refresh_from_db()

        self.assertEqual(self.task.status, 'awaiting_gate_2')
        output = PackagingOutput.objects.filter(task=self.task).first()
        self.assertIsNotNone(output, "PackagingOutput not created")
        self.assertTrue(output.spec_sheet, "Spec sheet should not be empty")

        print("\n✓ Gate 1 → Gate 2 assertions passed.")
        print(f"  PackagingOutput ID: {output.id}")
        print(f"  Pacdora URL: {output.pacdora_render_url}")
