from apps.pipeline.tests.quality_fixtures import critique, reviewed
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.core.models import Brand, ColorSystem, PackagingStructure, Product
from apps.pipeline.agents.aria import ARIAAgent
from apps.pipeline.models import (
    AgentLog,
    CreativeBrief,
    DesignTask,
    GeneratedImage,
    PackagingOutput,
)


# Phase 2A-2: the Creative Director emits the full structured design_intent/1.0
# document; ARIA still stores the legacy projection (3 directions) in CreativeBrief.
from apps.pipeline.tests.direction_fixtures import valid_document as _structured_document

MOCK_STRUCTURED = _structured_document()

# Phase 2A-4: exactly three variation prompts of the selected direction — the
# resume path fails closed on any other count. [His final goal, 2026-10-05, B4, re-pinned: "Three truly different
# concepts drawn straight away"] the first concepts: one prompt for each planned direction, its id echoed.
MOCK_PROMPTS = [
    {
        "direction_id": "d%d" % n,
        "direction_name": "Porcelain Verse",
        "full_prompt": f"variation {n}: tall slim porcelain-white carton, oversized "
                       f"serif name, rose gold foil, studio light",
        "aspect_ratio": "9:21",
        "notes": f"variation {n}",
    }
    for n in (1, 2, 3)
]


# Force a deterministic key state so vision is exercised the same way on every
# machine regardless of the developer's .env. Both keys are set because ARIA's
# pre-flight now fails fast when either is missing; qa_reviewer + the ARIA
# revision loop also branch on settings.ANTHROPIC_API_KEY at runtime (the
# provider calls themselves are mocked, so the values are never used for auth).
# §BH57(a)3: NO brand logo for these — they never meant to have one. The default BRAND_LOGO_PATH resolves
# to the REAL media/brand/logo.png, which these tests were silently reading; a lone logo now reaches the
# provider, so that accident would change their branch. This is what they always assumed.
@override_settings(ANTHROPIC_API_KEY="test-key", OPENAI_API_KEY="test-key",
                   BRAND_LOGO_PATH="/nonexistent/bh57/no-logo.png")
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

    # --- mock builders -----------------------------------------------------

    def _make_claude_response(self, json_data):
        mock_block = MagicMock()
        mock_block.type = 'text'
        mock_block.text = json.dumps(json_data)
        mock_resp = MagicMock()
        mock_resp.content = [mock_block]
        return mock_resp

    def _review(self, score):
        """Single-image QA review object (the current qa_reviewer contract)."""
        return self._make_claude_response(critique(score))

    def _make_openai_response(self):
        mock_data = MagicMock()
        mock_data.url = 'https://example.com/test_image.png'
        mock_resp = MagicMock()
        mock_resp.data = [mock_data]
        return mock_resp

    def _wire_common(self, mock_cd, mock_pe, mock_gen, mock_get):
        mock_cd.return_value = self._make_claude_response(MOCK_STRUCTURED)
        mock_pe.return_value = self._make_claude_response({'prompts': MOCK_PROMPTS})
        mock_gen.return_value = self._make_openai_response()
        mock_get.return_value = MagicMock(status_code=200, content=b'fake_png_bytes')

    def _run_to_gate1(self):
        """[His final goal, 2026-10-05, B4, re-pinned: "NO PROMPT STEP"] one run: the plan, then one picture for each
        direction, at Gate 1 — no direction asked of him (Phase 2A-4 paused here for one)."""
        ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()

    # --- tests -------------------------------------------------------------

    @patch('apps.pipeline.agents.image_producer.requests.get')
    @patch('apps.pipeline.agents.image_producer.openai.images.generate')
    @patch('apps.pipeline.agents.qa_reviewer.call_claude')
    @patch('apps.pipeline.agents.prompt_engineer.call_claude')
    @patch('apps.pipeline.agents.creative_director.call_claude')
    def test_full_pipeline_gate1(self, mock_cd, mock_pe, mock_qa, mock_gen, mock_get):
        """Pipeline runs start → Gate 1 with all agents mocked, QA passes."""
        self._wire_common(mock_cd, mock_pe, mock_gen, mock_get)
        mock_qa.return_value = self._review(8)

        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product,
            task_text='Create luxury packaging concept for Lip Oil',
            status='queued',
        )

        self._run_to_gate1()

        self.assertEqual(self.task.status, 'awaiting_gate_1')
        self.assertGreater(AgentLog.objects.filter(task=self.task).count(), 0)
        brief = CreativeBrief.objects.filter(task=self.task).first()
        self.assertIsNotNone(brief)
        self.assertEqual(len(brief.directions), 3)
        # [his final goal, B4, re-pinned] nothing chosen before Gate 1; the pictures one for each direction
        self.assertEqual(brief.selected_direction_id, "")
        self.assertEqual(sorted(GeneratedImage.objects.filter(task=self.task).values_list("direction_id", flat=True)),
                         ["d1", "d2", "d3"])
        images = GeneratedImage.objects.filter(task=self.task)
        self.assertEqual(images.count(), 3)
        self.assertTrue(images.first().qa_passed)

    @patch('apps.pipeline.agents.image_producer.requests.get')
    @patch('apps.pipeline.agents.image_producer.openai.images.generate')
    @patch('apps.pipeline.agents.qa_reviewer.call_claude')
    @patch('apps.pipeline.agents.prompt_engineer.call_claude')
    @patch('apps.pipeline.agents.creative_director.call_claude')
    def test_dieline_path_through_completed(self, mock_cd, mock_pe, mock_qa, mock_gen, mock_get):
        """Scenario-A dieline path: Gate 1 → dimensions → Gate 2 → completed,
        with the CMYK production PDF produced (no AI needed for dimensions)."""
        self._wire_common(mock_cd, mock_pe, mock_gen, mock_get)
        mock_qa.return_value = self._review(9)

        # Exact mm dims on the product → DielineAgent picks Scenario A (no AI).
        self.product.width_mm = Decimal('35.0')
        self.product.depth_mm = Decimal('30.0')
        self.product.height_mm = Decimal('100.0')
        self.product.product_type = 'carton'
        self.product.save()

        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product,
            task_text='Lip oil outer carton', status='queued',
        )

        # 1) run → direction selection → Gate 1
        self._run_to_gate1()
        self.assertEqual(self.task.status, 'awaiting_gate_1')

        # 2) approve image → dieline estimate → dimension gate
        image = GeneratedImage.objects.filter(task=self.task).first()
        ARIAAgent(self.task.id).resume_after_gate_1(image.id)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'awaiting_dimensions')

        output = PackagingOutput.objects.filter(task=self.task).first()
        self.assertIsNotNone(output)
        self.assertIsNotNone(output.dieline_job)

        # 3) confirm dimensions → geometry + exporters → Gate 2
        confirmed = {
            'width_mm': 35.0, 'depth_mm': 30.0, 'height_mm': 100.0,
            'bleed_mm': 3.0, 'safe_margin_mm': 4.0, 'glue_tab_mm': 10.0,
        }
        ARIAAgent(self.task.id).resume_after_dimensions(output.id, confirmed)
        self.task.refresh_from_db()
        output.refresh_from_db()

        self.assertEqual(self.task.status, 'awaiting_gate_2')
        self.assertTrue(output.dieline_file, 'SVG dieline not saved')
        self.assertTrue(output.production_pdf, 'CMYK production PDF not saved')
        self.assertTrue(output.spec_sheet.get('has_production_pdf'))
        self.assertIn('flat_width_mm', output.spec_sheet)
        # the saved PDF is a real PDF
        with output.production_pdf.open('rb') as fh:
            head = fh.read(5)
        self.assertTrue(head.startswith(b'%PDF'))

        # 4) approve Gate 2 → completed
        ARIAAgent(self.task.id).resume_after_gate_2(output.id)
        self.task.refresh_from_db()
        output.refresh_from_db()
        self.assertEqual(self.task.status, 'completed')
        self.assertTrue(output.is_final_approved)

    @patch('apps.pipeline.agents.image_producer.requests.get')
    @patch('apps.pipeline.agents.image_producer.openai.images.generate')
    @patch('apps.pipeline.agents.qa_reviewer.call_claude')
    @patch('apps.pipeline.agents.prompt_engineer.call_claude')
    @patch('apps.pipeline.agents.creative_director.call_claude')
    def test_revision_loop_runs_then_passes(self, mock_cd, mock_pe, mock_qa, mock_gen, mock_get):
        """First QA pass fails → one revision pass runs → second QA passes."""
        self._wire_common(mock_cd, mock_pe, mock_gen, mock_get)

        # 3 variation prompts → 3 images/pass → QA reviews each image. The whole
        # first pass fails, every later call passes.
        state = {'n': 0}

        def qa_side_effect(system, content, **kwargs):
            state['n'] += 1
            return self._review(5 if state['n'] <= 3 else 9)

        mock_qa.side_effect = qa_side_effect

        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product,
            task_text='Revision loop test', status='queued',
        )
        self._run_to_gate1()

        self.assertEqual(self.task.status, 'awaiting_gate_1')
        logs = AgentLog.objects.filter(task=self.task)
        self.assertTrue(logs.filter(action__icontains='revision pass 1').exists())
        self.assertFalse(logs.filter(action__icontains='revision pass 2').exists())
        # initial 3 variations + one 3-variation revision pass accumulate
        self.assertEqual(GeneratedImage.objects.filter(task=self.task).count(), 6)

    @patch('apps.pipeline.agents.image_producer.requests.get')
    @patch('apps.pipeline.agents.image_producer.openai.images.generate')
    @patch('apps.pipeline.agents.qa_reviewer.call_claude')
    @patch('apps.pipeline.agents.prompt_engineer.call_claude')
    @patch('apps.pipeline.agents.creative_director.call_claude')
    @override_settings(MAX_REVISION_PASSES=2)
    def test_revision_loop_respects_cap(self, mock_cd, mock_pe, mock_qa, mock_gen, mock_get):
        """QA never passes → revision loop stops at settings.MAX_REVISION_PASSES."""
        self._wire_common(mock_cd, mock_pe, mock_gen, mock_get)
        mock_qa.return_value = self._review(4)  # always fails

        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product,
            task_text='Revision cap test', status='queued',
        )
        self._run_to_gate1()

        self.assertEqual(self.task.status, 'awaiting_gate_1')
        logs = AgentLog.objects.filter(task=self.task)
        self.assertTrue(logs.filter(action__icontains='revision pass 1').exists())
        self.assertTrue(logs.filter(action__icontains='revision pass 2').exists())
        self.assertFalse(logs.filter(action__icontains='revision pass 3').exists())
        # (initial + 2 capped revision passes) x 3 variations = 9 images
        self.assertEqual(GeneratedImage.objects.filter(task=self.task).count(), 9)


def test_finding2_the_concept_check_judges_colours_by_the_briefs_as_his_ruling(tmp_path):
    """His test day finding 2 (2026-09-29, design 117): concepts 1 and 2 of his Playful Drip scored 4 and 5 under the
    pass line, first for a hot pink "not in any BBROSE canonical colour system" — the colour his brief asked for. The
    check was never shown the brief's colours and judged every palette by the house four. It is now shown them, told
    his ruling of finding 1, and judges a brief naming none as before; the rescue requires mean ≥8 and critical dimensions ≥7."""
    from types import SimpleNamespace

    from PIL import Image

    from apps.pipeline.agents import qa_reviewer as qa
    from apps.pipeline.services.concept_quality import evaluate
    picture = tmp_path / "concept.png"
    Image.new("RGB", (8, 8), (233, 30, 140)).save(picture)
    image = SimpleNamespace(id=1, direction_name="Playful Drip", variation_number=1, prompt_used="a tube")
    seen = []

    def answer(system, content, **_kwargs):
        seen.append((system, next(part["text"] for part in content if part.get("type") == "text")))
        reply = critique(8)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(reply))])

    with patch.object(qa, "call_claude", side_effect=answer):
        for colours in (["hot pink", "soft pink", "gold"], []):
            agent = qa.QAReviewerAgent([], brand_id=None,
                                       product_profile={"name": "Coconut Rose Body Lotion", "preferred_colors": colours})
            agent.vision_enabled = True
            verdict = evaluate(agent._vision_review(image, str(picture), "BBROSE brand standards"))
            assert verdict["review_status"] == "accepted" and verdict["passed"] and verdict["score"] == 8
    (system, told), (_system, untold) = seen
    system = " ".join(system.split())                      # the instructions as read, their line breaks aside
    assert "## The brief's colours — they win (the owner's ruling)\nhot pink; soft pink; gold\n" in told
    assert "with the BBROSE logo and at most one house accent beside them" in told
    assert "The brief's colours" not in untold
    assert "The brief's colours, mood, form, dimensions, languages and copy take precedence" in system
    assert "Clear glass and chrome are materials, not inks" in system
    assert "monochrome directions are allowed" in system
    assert not evaluate(critique(7.9))["passed"]


def test_his_answer_the_concept_checks_mood_follows_the_briefs_own(tmp_path):
    """His answer 4 of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6badb27): "the concept check's mood follows
    the brief". The check is shown the brief's own mood under its own heading and told to judge the register against it;
    a brief with no mood is judged as before, by the house's register."""
    from types import SimpleNamespace

    from PIL import Image

    from apps.pipeline.agents import qa_reviewer as qa
    picture = tmp_path / "concept.png"
    Image.new("RGB", (8, 8), (233, 30, 140)).save(picture)
    image = SimpleNamespace(id=1, direction_name="Playful Drip", variation_number=1, prompt_used="a tube")
    seen = []

    def answer(system, content, **_kwargs):
        seen.append(next(part["text"] for part in content if part.get("type") == "text"))
        reply = critique(8)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(reply))])
    mood = "playful, retro, sweet — a candy-shop drip, loud and happy."
    with patch.object(qa, "call_claude", side_effect=answer):
        for profile in ({"name": "Coconut Rose Body Lotion", "mood": mood}, {"name": "Coconut Rose Body Lotion"}):
            agent = qa.QAReviewerAgent([], brand_id=None, product_profile=profile)
            agent.vision_enabled = True
            agent._vision_review(image, str(picture), "BBROSE brand standards")
    told, untold = seen
    assert "## The brief's mood — judge the register against it (the owner's ruling)\n" + mood + "\n" in told
    assert "The brief's mood" not in untold
