from apps.pipeline.models import DesignTask, AgentLog, CreativeBrief
from apps.pipeline.agents.creative_director import CreativeDirectorAgent
from apps.pipeline.agents.prompt_engineer import PromptEngineerAgent
from apps.pipeline.agents.image_producer import ImageProducerAgent
from apps.pipeline.agents.qa_reviewer import QAReviewerAgent
import json


class ARIAAgent:

    def __init__(self, task_id):
        self.task = DesignTask.objects.get(id=task_id)
        self.brand_id = self.task.brand.id

    def log(self, action, payload=None, agent='ARIA', level='info'):
        AgentLog.objects.create(
            task=self.task,
            agent_name=agent,
            action=action,
            payload=payload,
            level=level
        )

    def run(self):
        try:
            self.task.status = 'running'
            self.task.save()
            self.log("ARIA: pipeline started")

            # STAGE 1: Creative Director
            self.log("ARIA: delegating to Creative Director", agent='ARIA')
            cd_agent = CreativeDirectorAgent(
                self.task, self.brand_id,
                log_fn=lambda msg, data=None, level='info': self.log(msg, data, agent='CreativeDirector', level=level)
            )
            directions = cd_agent.run()

            if not directions:
                self._fail("Creative Director produced no directions")
                return

            # STAGE 2: Prompt Engineer
            self.log("ARIA: delegating to Prompt Engineer", agent='ARIA')
            structure_id = None
            if self.task.product and self.task.product.packaging_structure:
                structure_id = self.task.product.packaging_structure.structure_id

            pe_agent = PromptEngineerAgent(
                directions, structure_id,
                log_fn=lambda msg, data=None, level='info': self.log(msg, data, agent='PromptEngineer', level=level)
            )
            prompts = pe_agent.run()

            # STAGE 3: Image Producer
            self.log("ARIA: delegating to Image Producer", agent='ARIA')
            ip_agent = ImageProducerAgent(
                self.task, prompts,
                log_fn=lambda msg, data=None, level='info': self.log(msg, data, agent='ImageProducer', level=level)
            )
            images = ip_agent.run()

            if not images:
                self._fail("Image Producer generated no images")
                return

            # STAGE 4: QA Reviewer
            self.log("ARIA: delegating to QA Reviewer", agent='ARIA')
            qa_agent = QAReviewerAgent(
                images, self.brand_id,
                log_fn=lambda msg, data=None, level='info': self.log(msg, data, agent='QAReviewer', level=level)
            )
            qa_results = qa_agent.run()

            # Save brief to database. update_or_create (not create) so a
            # Gate 1 rejection can re-run the pipeline — CreativeBrief.task
            # is OneToOne, so a plain create() would IntegrityError on revision.
            CreativeBrief.objects.update_or_create(
                task=self.task,
                defaults={"directions": directions},
            )

            # GATE 1 — pause for human decision
            self.task.status = 'awaiting_gate_1'
            self.task.save()
            self.log("ARIA: reached Gate 1 — awaiting your approval")

        except Exception as e:
            self._fail(str(e))

    def resume_after_gate_1(self, approved_image_id):
        """Called when you approve an image at Gate 1.

        Dispatches to the configured packaging backend (settings.PACKAGING_BACKEND):
        the dieline generator (default) or the legacy Pacdora scraper.
        """
        from django.conf import settings
        from apps.pipeline.models import GeneratedImage

        image = GeneratedImage.objects.get(id=approved_image_id)
        image.is_approved = True
        image.save()

        self.task.status = 'gate_1_approved'
        self.task.save()
        self.log(f"ARIA: Gate 1 approved — image {approved_image_id}")

        backend = getattr(settings, 'PACKAGING_BACKEND', 'dieline')
        if backend == 'pacdora':
            self._run_pacdora(image)
        else:
            self._run_dieline_estimate(image)

    def _run_pacdora(self, image):
        """Legacy path: Pacdora produces a 3D render, then jump to Gate 2."""
        from apps.pipeline.agents.pacdora_agent import PacdoraAgent

        pacdora_agent = PacdoraAgent(
            self.task, image,
            log_fn=lambda msg, data=None, level='info': self.log(msg, data, agent='Pacdora', level=level)
        )
        pacdora_agent.run()

        self.task.status = 'awaiting_gate_2'
        self.task.save()
        self.log("ARIA: reached Gate 2 — awaiting 3D mockup approval")

    def _run_dieline_estimate(self, image):
        """Dieline path: estimate dimensions, then pause for human confirmation."""
        from apps.pipeline.agents.dieline_agent import DielineAgent
        from apps.pipeline.models import PackagingOutput

        agent = DielineAgent(
            self.task,
            log_fn=lambda msg, data=None, level='info': self.log(msg, data, agent='Dieline', level=level)
        )
        result, job = agent.run()

        PackagingOutput.objects.create(
            task=self.task,
            approved_image=image,
            spec_sheet=self._build_dieline_spec(result),
            dieline_job=job,
        )

        self.task.status = 'awaiting_dimensions'
        self.task.save()
        self.log("ARIA: reached dimension gate — confirm carton dimensions to generate the dieline")

    def _build_dieline_spec(self, result):
        product = self.task.product
        return {
            'backend': 'dieline',
            'template': 'straight_tuck_end_carton',
            'scenario': result.scenario,
            'product_name': product.name if product else 'Unknown',
            'product_type': getattr(product, 'product_type', '') if product else '',
            'estimated_dimensions': result.model_dump(),
        }

    def resume_after_dimensions(self, packaging_output_id, confirmed_dims):
        """Called when you confirm dimensions at the dimension gate.

        Runs the deterministic geometry engine + exporters, saves the dieline
        files onto the PackagingOutput, then advances to Gate 2.
        """
        from apps.pipeline.agents.dieline_agent import DielineAgent
        from apps.pipeline.models import PackagingOutput
        from django.core.files.base import ContentFile

        output = PackagingOutput.objects.get(id=packaging_output_id)
        job = output.dieline_job
        if job is None:
            self._fail("No dieline job linked to this output")
            return

        self.task.status = 'generating_dieline'
        self.task.save()
        self.log("ARIA: dimensions confirmed — generating dieline")

        agent = DielineAgent(
            self.task,
            log_fn=lambda msg, data=None, level='info': self.log(msg, data, agent='Dieline', level=level)
        )
        product = self.task.product
        metadata = {
            'product_name': product.name if product else self.task.task_text[:60],
            'product_type': getattr(product, 'product_type', '') if product else '',
            'notes': self.task.task_text,
        }

        try:
            gen = agent.generate(job, confirmed_dims, metadata)
        except Exception as e:
            # Recoverable: send the task back to the dimension gate so the user
            # can correct values, rather than failing the whole pipeline.
            spec = output.spec_sheet or {}
            spec['generation_error'] = str(e)
            output.spec_sheet = spec
            output.save(update_fields=['spec_sheet'])
            self.task.status = 'awaiting_dimensions'
            self.task.save()
            self.log(f"Dieline: generation failed — {e}", agent='Dieline', level='error')
            return

        output.dieline_file.save(
            f"dieline_task_{self.task.id}.svg",
            ContentFile(gen['svg_string'].encode('utf-8')),
            save=False,
        )
        if gen.get('ai_path'):
            with open(gen['ai_path'], 'rb') as f:
                output.dieline_ai_file.save(
                    f"dieline_task_{self.task.id}.ai",
                    ContentFile(f.read()),
                    save=False,
                )
        spec = output.spec_sheet or {}
        spec.pop('generation_error', None)
        spec['confirmed_dimensions'] = confirmed_dims
        spec['flat_width_mm'] = gen['flat_width_mm']
        spec['flat_height_mm'] = gen['flat_height_mm']
        spec['panel_count'] = gen['panel_count']
        spec['warnings'] = gen['warnings']
        output.spec_sheet = spec
        output.save()

        self.task.status = 'awaiting_gate_2'
        self.task.save()
        self.log("ARIA: dieline ready — awaiting Gate 2 approval")

    def resume_after_gate_2(self, packaging_output_id):
        """Called when you approve the 3D mockup at Gate 2."""
        from apps.pipeline.models import PackagingOutput

        output = PackagingOutput.objects.get(id=packaging_output_id)
        output.is_final_approved = True
        output.save()

        self.task.status = 'completed'
        self.task.save()
        self.log("ARIA: pipeline completed — all outputs saved")

    def _fail(self, reason):
        import logging
        logging.getLogger('aria').error(f'Task {self.task.id} failed: {reason}')
        self.task.status = 'failed'
        self.task.save()
        self.log(f"ARIA: pipeline failed — {reason}", level='error')
