from django.conf import settings
from django.db import models

from apps.pipeline.targets.base import DesignTarget

TASK_STATUS = [
    ('queued', 'Queued'),
    ('running', 'Running'),
    # §BH71 PART 2: the design's trend board is shown — its pictures ticked, one click unticking one — while the review
    # window is open; the directions are made with the ticked pictures' words when he presses on or the window
    # closes. Deliberately NOT a gate, and not a wait on a person: the design moves on by itself.
    ('awaiting_trend_review', 'Awaiting Trend Review'),
    # Phase 2A-4: pre-render creative-planning pause — Design Intent + three
    # directions exist, nothing is selected, no prompt or image work has run.
    # Deliberately NOT a gate: choosing a reasoning direction is not approval.
    ('awaiting_direction_selection', 'Awaiting Direction Selection'),
    ('awaiting_gate_1', 'Awaiting Gate 1'),
    ('gate_1_approved', 'Gate 1 Approved'),
    ('awaiting_dimensions', 'Awaiting Dimension Confirmation'),
    ('awaiting_container_profile', 'Awaiting Container Profile'),
    # 2C-2 closeout: terminal-but-reviewable container stage after a FINAL
    # human Gate-2 visual rejection (live pilot). Never retryable, never
    # advances to Packaging; every output and decision stays reviewable.
    ('container_stage_visually_rejected', 'Container Stage Visually Rejected'),
    # Phase 2A-6: technical structure confirmation — the clean dieline exists
    # and a human must confirm the STRUCTURE (panel sequence, closure,
    # compensation assumptions) before any artwork is composed onto it.
    # Deliberately NOT a gate: it approves no design, only the die.
    ('awaiting_structure_confirmation', 'Awaiting Structure Confirmation'),
    # PALT-M4C-4: the engine has read a selected design and drafted an
    # intent; a human must confirm WHAT THE ENGINE UNDERSTOOD before that
    # reading is allowed to drive geometry. Only confirmed intent is design
    # authority, so this state exists to stop a draft flowing onward.
    ('awaiting_design_intent_confirmation',
     'Awaiting Design Intent Confirmation'),
    # PALT-M4C-4: the reading is confirmed. Deliberately NOT
    # gate_1_approved — confirming what the engine understood approves a
    # READING, not the design, and must not advance anything keyed off a
    # real gate.
    ('design_intent_confirmed', 'Design Intent Confirmed'),
    ('generating_dieline', 'Generating Dieline'),
    ('awaiting_gate_2', 'Awaiting Gate 2'),
    ('gate_2_approved', 'Gate 2 Approved'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
    ('rejected', 'Rejected'),
    # 2C-2C-CORR-1 §9: direction selected but the Gate-1 generation
    # configuration (variation spec / references / influence plan / budget)
    # is incomplete — generation may not be enqueued from this state.
    ('awaiting_gate1_generation_configuration',
     'Awaiting Gate-1 Generation Configuration'),
]


PROJECT_STATUS = [
    ('container', 'Container Stage'),
    ('packaging', 'Packaging Stage'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
]

STAGE_CHOICES = [
    ('container', 'Container'),
    ('packaging', 'Packaging'),
]


class DesignProject(models.Model):
    """Parent coordinating multiple DesignTasks for a COMPOSITE target
    (Phase C). Complete Product orchestrates a Product Container stage then a
    Packaging stage. The project holds the shared brief and a coarse stage
    status; it never duplicates per-task state. Single-target tasks have no
    project."""
    brand = models.ForeignKey('core.Brand', on_delete=models.CASCADE,
                              related_name='projects')
    product = models.ForeignKey('core.Product', null=True, blank=True,
                                on_delete=models.SET_NULL)
    brief = models.TextField()
    design_target = models.CharField(max_length=32,
                                     default=DesignTarget.COMPLETE_PRODUCT.value)
    status = models.CharField(max_length=20, choices=PROJECT_STATUS,
                              default='container')
    # Which stage last failed, for resume clarity (Phase C2). Blank when fine.
    failed_stage = models.CharField(max_length=20, blank=True, default='')
    # 2C-1 §5/§8/§9: bounded coordinator records — stage handoff records
    # (complete_product_stage_handoff/1.0), the computed rich project-state
    # projection, and advancement idempotency identities. Additive JSON; the
    # stage tasks remain the source of truth.
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


#: [his answers after 122 was redrawn, 2026-10-08, (1)] the longest SKU a design keeps
SKU_MAX_LENGTH = 64


def clean_sku(value) -> str:
    """An SKU as he typed it: its spaces closed, at most SKU_MAX_LENGTH characters; '' for none."""
    return " ".join(str(value or "").split())[:SKU_MAX_LENGTH]


class DesignTask(models.Model):
    brand = models.ForeignKey('core.Brand', on_delete=models.CASCADE)
    product = models.ForeignKey('core.Product', null=True, blank=True, on_delete=models.SET_NULL)
    campaign = models.ForeignKey('core.Campaign', null=True, blank=True, on_delete=models.SET_NULL)
    task_text = models.TextField()  # what you typed
    # Design Target (Phase A, 2026-07-08): what the shared pipeline produces.
    # Defaults to packaging — the entire existing corpus — so the target
    # refactor is invisible. New targets activate via apps.pipeline.targets.
    design_target = models.CharField(
        max_length=32, choices=DesignTarget.choices,
        default=DesignTarget.PACKAGING.value)
    status = models.CharField(max_length=50, choices=TASK_STATUS, default='queued')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    gate_1_notes = models.TextField(blank=True)  # your feedback if rejected
    gate_2_notes = models.TextField(blank=True)
    # Why the task failed — shown in the dashboard next to the Retry button.
    error_message = models.TextField(blank=True)
    # [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (11): "in a test mode that draws ONE concept instead of
    # three", and (2): "let me continue 125 ... at $0"] the executor's options for one design, set where the design is
    # made or continued by him — never by the New design form, never a default: ``one_concept`` (the three directions
    # planned, one concept drawn — his test runs, marked so), ``spend_held`` (every paid call refused before it is made,
    # said — a design continued at $0)
    # [His goal after the pitch page, 2026-10-15, B (9)] and ``autopilot`` — the pitch run, set by the one tick he gives
    # beside Start: every step that waits on a person taken by the system itself, stopping at Gate 2
    # (apps/pipeline/autopilot.py)
    options = models.JSONField(default=dict, blank=True)
    # Ownership (Milestone 11.1 / audit H2). Nullable for pre-Phase-11 rows and
    # for system-created tasks (seed commands); SET_NULL keeps the task when a
    # user account is deleted.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_tasks',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='assigned_tasks',
    )
    # Manual image-only reruns done at Gate 1 (Milestone 11.3), bounded by the
    # same persistent revision cap as the automatic QA loop; planning never
    # resets already consumed attempts.
    image_rerun_count = models.PositiveIntegerField(default=0)
    # Campaign/batch run this task was fanned out from (Milestone 12.5); null
    # for individually-created tasks.
    batch = models.ForeignKey(
        'BatchRun', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='tasks',
    )
    # Composite parent (Phase C): set only for a stage of a Complete Product
    # (or future composite). Single-target tasks stay project=None, stage="".
    project = models.ForeignKey(
        'DesignProject', null=True, blank=True,
        on_delete=models.CASCADE, related_name='tasks',
    )
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, blank=True, default='')
    # [His answers after 122 was redrawn, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 0b0c7e7), (1): "Add an
    # optional SKU field on New design and at Gate 2 so I can fill it in any time."] the SKU he typed for a design that has
    # no product record — empty until he gives one; a product record's own SKU stands (``sku_on_record``)
    sku = models.CharField(max_length=SKU_MAX_LENGTH, blank=True, default='')

    def sku_on_record(self) -> str:
        """The design's SKU: its product record's, else the one he typed for it — on New design or at Gate 2 — else its
        project's (a Complete Product's carton is started after he typed it on the tube); '' where none is given."""
        own = " ".join(str(getattr(self.product, "product_id", "") or "").split()) if self.product_id else ""
        if own:
            return own
        if self.sku:
            return self.sku
        return str(((self.project.metadata or {}).get("sku") or "") if self.project_id else "")

    def current_output(self):
        """[His test blocker on design 124, 2026-10-11, (4): "stop and tell me which part and why, with options"] the
        design's current output: its newest. A design whose concept is approved again at Gate 1 — after a stop, by his
        choice of the same concept or another — is given a new output, drawn on it; every door reads that one, never the
        first it was given (found redrawing 124: his size was confirmed on its stopped output, which held no map)."""
        return self.packaging_outputs.order_by("-pk").first()

    class Meta:
        # At most one child per stage of a project (Phase C2): the DB guard
        # against duplicate packaging tasks from concurrent completions/retries.
        # NULL project rows (all single-target tasks) don't collide in SQL.
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'stage'], name='uniq_project_stage'),
        ]


class TaskReference(models.Model):
    """User-uploaded reference material for a task (Phase B4b).

    Optional inputs supplied at creation — a container photo, logo, existing
    label artwork, inspiration images, colour references. Used two ways:
    grounding the concept generation, and (for containers) preferring an
    uploaded logo/label/container over the defaults during reconstruction.
    They are ALWAYS "Reference Only" — never the final artwork.
    """
    # PALT-M4C §3: palette targets need their own reference vocabulary.
    # A palette concept is not a "container photo" and a pan-layout
    # reference is not "inspiration"; collapsing them was part of why the
    # palette engine could not use supplied design information.
    REF_KINDS = [
        ('container', 'Container photo'),
        ('logo', 'Logo'),
        ('label', 'Label artwork'),
        ('inspiration', 'Inspiration'),
        ('color', 'Colour reference'),
        # palette-specific
        ('palette_concept', 'Palette concept'),
        ('palette_product', 'Palette product reference'),
        ('outer_case', 'Outer-case reference'),
        ('pan_layout', 'Pan-layout reference'),
        ('hinge', 'Hinge reference'),
        ('clasp', 'Clasp reference'),
        ('mirror', 'Mirror reference'),
        ('powder_finish', 'Powder-finish reference'),
        ('artwork', 'Artwork reference'),
        ('typography', 'Typography'),
        ('material', 'Material reference'),
        # §BH69(2): an inspiration picture the owner attaches — READ INTO WORDS and never a provider input (the
        # older 'inspiration' is the Complete Product's hand-off of its approved concept, the house's own design)
        ('inspiration_picture', 'Inspiration picture'),
        # [his final goal, 2026-10-05, B1: "An "Inside reference" picture slot beside the inspiration box (one or more
        # pictures)."] read ONCE into its pattern and style for the carton's inside — never a provider input, never drawn
        ('inside_reference', 'Inside reference'),
        # [his final goal, 2026-10-05, B3: "Custom sticker: follows a sticker reference picture or the brief's words."]
        ('sticker_reference', 'Sticker reference'),
    ]
    SOURCE_CHOICES = [('USER_UPLOAD', 'User upload')]
    STATUS_CHOICES = [('REFERENCE_ONLY', 'Reference only')]

    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE,
                             related_name='references')
    kind = models.CharField(max_length=20, choices=REF_KINDS)
    # B4b-1: FileField, not ImageField. .pdf, .ai and .eps are legitimate
    # references and an ImageField rejects all three by trying to decode them
    # as images. Type safety did not weaken - it moved to
    # apps.pipeline.references, which checks the file SIGNATURE rather than
    # trusting either the extension or the browser's Content-Type.
    image = models.FileField(upload_to='task_refs/')
    original_filename = models.CharField(max_length=160, blank=True, default='')
    media_type = models.CharField(max_length=80, blank=True, default='')
    file_size = models.PositiveIntegerField(default=0)
    ordering = models.PositiveIntegerField(default=0)
    # §BH69(2): the stored file's sha256 — an inspiration picture's reading is found by it (InspirationReading)
    sha256 = models.CharField(max_length=64, blank=True, default='', db_index=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES,
                              default='USER_UPLOAD')
    # Stored rather than hardcoded in a template: the badge should render a
    # fact the row carries, so it cannot be dropped by a UI edit.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default='REFERENCE_ONLY')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordering', 'id']


class AgentLog(models.Model):
    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE, related_name='logs')
    agent_name = models.CharField(max_length=100)  # ARIA, CreativeDirector, etc.
    action = models.TextField()  # human-readable: "Retrieved 4 similar products"
    payload = models.JSONField(null=True, blank=True)  # raw data
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=20, default='info')  # info, warning, error
    # The human who triggered the event (retry, reject, rerun, prompt edit) —
    # null for agent-originated entries (Milestone 11.1).
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='agent_logs',
    )


GATE_CHOICES = [
    ('gate_1', 'Gate 1'),
    ('dimension', 'Dimension Gate'),
    ('gate_2', 'Gate 2'),
    # PALT-M4C-4. A design-intent confirmation is not Gate 1 or Gate 2 and
    # must never be mistaken for either: it approves a READING of a design,
    # not the design and not the production data.
    ('design_intent', 'Design Intent Confirmation'),
]

DECISION_CHOICES = [
    ('approve', 'Approve'),
    ('reject', 'Reject'),
]


class GateDecision(models.Model):
    """Immutable audit trail for every human gate decision (Milestone 11.1 /
    audit H2). The task's status fields stay for pipeline compatibility; who
    decided what, when, and why lives here. Rejection notes are preserved here
    permanently even after DesignTask.gate_*_notes are cleared on approval
    (Milestone 11.3 / audit H10)."""
    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE, related_name='gate_decisions')
    gate = models.CharField(max_length=20, choices=GATE_CHOICES)
    decision = models.CharField(max_length=10, choices=DECISION_CHOICES)
    notes = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='gate_decisions',
    )
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['decided_at']


class CreativeBrief(models.Model):
    task = models.OneToOneField(DesignTask, on_delete=models.CASCADE, related_name='brief')
    retrieved_products = models.JSONField(default=list)  # similar products found
    retrieved_references = models.JSONField(default=list)
    directions = models.JSONField()  # list of 3-5 direction objects
    # Legacy briefs: {name, rationale, palette, material, finish, prompt_seed}.
    # Phase 2A-4 briefs: canonical design_intent/1.1 direction cards.
    # Phase 2A-4: the design_intent/1.1 document MINUS its directions (which live
    # above). Resume reassembles {**design_intent, "directions": directions} and
    # re-validates before any use. Empty dict = legacy task, no new workflow.
    design_intent = models.JSONField(default=dict, blank=True)
    # Selection binds to the STABLE direction_id ("d1"...), never a list index —
    # display order carries no authority.
    selected_direction_id = models.CharField(max_length=64, blank=True, default='')
    direction_selected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class GeneratedImage(models.Model):
    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE, related_name='images')
    direction_name = models.CharField(max_length=200)
    # [his final goal, 2026-10-05, B4: "Three truly different concepts drawn straight away ... He picks a picture."]
    # the planned direction this picture was drawn for, by its stable id ("" — a picture drawn before)
    direction_id = models.CharField(max_length=64, blank=True, default="")
    prompt_used = models.TextField()
    # TextField, not URLField: OpenAI signed URLs routinely exceed 500 chars.
    # This is the provider's expiring URL — never served to the frontend; the
    # durable copy lives in image_file (see serializers / Milestone 8.6).
    image_url = models.TextField(blank=True)
    image_file = models.ImageField(upload_to='generated/', blank=True)
    # Set when the local download failed after retries — the UI shows a
    # retryable placeholder instead of a broken (expired) remote URL.
    download_failed = models.BooleanField(default=False)
    variation_number = models.IntegerField(default=1)  # 1, 2, or 3
    # Set when a newer generation pass replaced this image (Milestone 11.3):
    # history is kept, never deleted, and the API returns the current set by
    # default (?include_superseded=1 for the full history).
    superseded = models.BooleanField(default=False)
    qa_passed = models.BooleanField(default=False)
    qa_notes = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    # Phase 2A-6E §9: an explicit user verdict on a kept image (e.g.
    # "REJECTED_BY_USER — INSUFFICIENT_VISUAL_RICHNESS"). Audit history —
    # the image and its file are preserved, never deleted.
    user_rejection_label = models.CharField(max_length=200, blank=True, default="")
    # Phase 2A-6E §8: what actually reached the image provider for THIS
    # render — approved concept-reference IDs, the visual files passed, the
    # influence-plan hash and the variation identity. A render must never
    # claim material influence this field does not evidence.
    reference_provenance = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ConceptReference(models.Model):
    """A material-library item offered — and possibly USER-approved — as a
    CONCEPT reference for one task (Phase 2A-6E §3/§4).

    Concept-reference permission is narrow and task-scoped.
    USER_APPROVED_FOR_CONCEPT_REFERENCE allows: showing the item to the
    Prompt Engineer, passing it visually to the concept image generator, and
    analyzing its palette / composition / motif / typography / finish
    language as non-production inspiration for THIS task. It never allows:
    copying or reproducing the design, using it as production artwork,
    placing it into the final .ai, vectorizing it automatically, treating it
    as a canonical brand asset, granting reusable-production permission, or
    changing ownership/licence status. Machine code never sets APPROVED —
    approval is a human action through the API.
    """
    PERMISSION_CANDIDATE = "CANDIDATE"
    PERMISSION_APPROVED = "USER_APPROVED_FOR_CONCEPT_REFERENCE"
    PERMISSION_DECLINED = "DECLINED"
    PERMISSION_CHOICES = [
        (PERMISSION_CANDIDATE, PERMISSION_CANDIDATE),
        (PERMISSION_APPROVED, PERMISSION_APPROVED),
        (PERMISSION_DECLINED, PERMISSION_DECLINED),
    ]
    SOURCE_HISTORICAL = "HISTORICAL_DESIGN_REFERENCE"
    SOURCE_MATERIAL_LIBRARY = "MATERIAL_LIBRARY"

    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE,
                             related_name='concept_references')
    source_type = models.CharField(max_length=40)
    library_item_id = models.CharField(max_length=300)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    relevance_reason = models.CharField(max_length=300, blank=True)
    retrieval_score = models.FloatField(default=0.0)
    # DIP discipline: machine never asserts ownership or rights; defaults are
    # the unverified states and only a human review changes them (elsewhere —
    # never through this model).
    ownership_status = models.CharField(max_length=60,
                                        default="OWNERSHIP_UNCONFIRMED")
    rights_status = models.CharField(max_length=60, default="RIGHTS_UNREVIEWED")
    is_vector = models.BooleanField(default=False)
    #: which root image_path is relative to: "media" (MEDIA_ROOT) or
    #: "materials" (the read-only materials library root).
    image_root = models.CharField(max_length=20, default="media")
    image_path = models.CharField(max_length=500)
    permission_status = models.CharField(
        max_length=60, choices=PERMISSION_CHOICES, default=PERMISSION_CANDIDATE)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                    blank=True, on_delete=models.SET_NULL,
                                    related_name='+')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('task', 'library_item_id')]
        ordering = ['-retrieval_score', 'id']

    @property
    def production_use_allowed(self) -> bool:
        """Structurally false: concept-reference permission NEVER implies
        production use. There is deliberately no field to flip."""
        return False


class Gate1RegenerationJob(models.Model):
    """One versioned, pollable reference-grounded Gate-1 regeneration
    (2A-6E-CORR-2 §4). The click's whole lifecycle is observable: the
    endpoint creates exactly one active job per task (repeated clicks are
    idempotent and return the same job), the Celery worker moves it through
    queued → running → completed/failed, and the UI polls the job id —
    never inferring success from a 200."""
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    ACTIVE_STATUSES = (STATUS_QUEUED, STATUS_RUNNING)

    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE,
                             related_name='regeneration_jobs')
    direction_id = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default=STATUS_QUEUED)
    approved_reference_ids = models.JSONField(default=list)
    influence_plan_hash = models.CharField(max_length=64)
    variation_identities = models.JSONField(default=list)
    celery_task_id = models.CharField(max_length=64, blank=True, default="")
    #: 2A-6E-CORR-7: the validated gate1_reference_regeneration_prompts/1.0
    #: payload of a completed run — the structured record downstream
    #: reconstruction reads to preserve the SELECTED variation's design.
    prompts_payload = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.SET_NULL,
                                   related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-id']


class ConceptInfluencePlan(models.Model):
    """The structured influence plan (material_influence_plan/1.0) built from
    a task's user-approved concept references (Phase 2A-6E §5). Describes
    design PRINCIPLES to borrow — never a layout to reproduce — and contains
    no file locator of any kind (enforced by the builder)."""
    task = models.OneToOneField(DesignTask, on_delete=models.CASCADE,
                                related_name='concept_influence_plan')
    schema_version = models.CharField(max_length=60,
                                      default="material_influence_plan/1.0")
    plan = models.JSONField()
    plan_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.SET_NULL,
                                   related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)


class PackagingOutput(models.Model):
    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE, related_name='packaging_outputs')
    approved_image = models.ForeignKey(GeneratedImage, on_delete=models.CASCADE)
    spec_sheet = models.JSONField()  # {structure, dimensions, material, finish, color_codes}
    pacdora_render_url = models.URLField(blank=True)
    dieline_file = models.FileField(upload_to='dielines/', blank=True)  # SVG (dieline backend)
    dieline_ai_file = models.FileField(upload_to='dielines/', blank=True)  # Illustrator .ai (best-effort)
    production_pdf = models.FileField(upload_to='dielines/', blank=True)  # CMYK prepress PDF (factory deliverable)
    # Design-on-dieline preview (P4, 2026-07-04): the approved concept artwork
    # composited onto the display panels — the "finished product" visual a
    # reviewer approves and downloads. Preview-grade RGB, NOT the print file.
    design_preview = models.FileField(upload_to='dielines/', blank=True)     # PNG snapshot of the .ai
    design_preview_ai = models.FileField(upload_to='dielines/', blank=True)  # .ai
    dieline_job = models.ForeignKey(
        'dielines.DielineJob', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='packaging_outputs',
    )
    spec_pdf = models.FileField(upload_to='spec_sheets/', blank=True)
    is_final_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # At most one final-approved output per task (Milestone 8.3).
            models.UniqueConstraint(
                fields=['task'],
                condition=models.Q(is_final_approved=True),
                name='unique_final_packaging_output_per_task',
            ),
        ]


class ApiCallRecord(models.Model):
    """Cost ledger row — one per external AI API call (Milestone 12.2).

    Written by the Claude service (per messages.create) and the image producer
    (per image). ``cost_usd`` is computed at write time from the per-model
    prices in settings so historical rows are stable even if prices change.
    """
    # [§BH71 PART 2: and one per Tavily search — its spend sat outside every budget guard]
    PROVIDER_CHOICES = [('anthropic', 'Anthropic'), ('openai', 'OpenAI'), ('tavily', 'Tavily')]

    task = models.ForeignKey(
        DesignTask, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='api_calls',
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    model = models.CharField(max_length=80)
    operation = models.CharField(max_length=80, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    image_count = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    # 2B-3V §8 observability: per-call provenance the ledger could not express
    # in scalar columns — provider_request_id / provider_operation_id (or the
    # literal PROVIDER_REQUEST_ID_NOT_RETURNED), start/end timestamps,
    # latency_ms, retry_number, prompt_hash, reference_ids and the actual
    # visual filenames passed. Additive JSON: one column, no schema per field.
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.provider}/{self.model} {self.operation} ${self.cost_usd}"


# Notification kinds map 1:1 to the task statuses that warrant a nudge.
# §BH55 Phase 3 (survey rows 6.25, 7.8): EVERY step that waits on a person. The five kinds told a designer about three
# of them and said nothing when a design reached its direction step, its container's shape, its structure step, its
# design intent or a held generation — the very steps a design sits at, unheard, until someone opens it. The names are
# the statuses' own (apps/dashboard/words.py says each in words); the longest is 39 characters, so the field holds 50.
NOTIFICATION_KINDS = [
    ('awaiting_direction_selection', 'Awaiting a direction'),
    ('awaiting_gate1_generation_configuration', 'Awaiting the concept set-up'),
    ('awaiting_gate_1', 'Awaiting Gate 1'),
    ('awaiting_dimensions', 'Awaiting Dimensions'),
    ('awaiting_container_profile', 'Awaiting the container shape'),
    ('awaiting_structure_confirmation', 'Awaiting the structure'),
    ('awaiting_design_intent_confirmation', 'Awaiting the design intent'),
    ('awaiting_gate_2', 'Awaiting Gate 2'),
    ('failed', 'Task Failed'),
    ('completed', 'Task Completed'),
]


class Notification(models.Model):
    """In-app notification (Milestone 12.4). One row per recipient per event —
    rendered in the dashboard bell menu; ``kind`` mirrors the task status that
    triggered it."""
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications',
    )
    task = models.ForeignKey(
        DesignTask, null=True, blank=True,
        on_delete=models.CASCADE, related_name='notifications',
    )
    kind = models.CharField(max_length=50, choices=NOTIFICATION_KINDS)   # §BH55 Phase 3: the longest name is 39
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['recipient', 'is_read'])]

    def __str__(self):
        return f"{self.recipient} · {self.kind}"


class BatchRun(models.Model):
    """A campaign/batch run (Milestone 12.5): one fan-out of DesignTasks, one
    per product, sharing a brief override. Tasks link back via DesignTask.batch."""
    brand = models.ForeignKey('core.Brand', on_delete=models.CASCADE, related_name='batch_runs')
    campaign = models.ForeignKey(
        'core.Campaign', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='batch_runs',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='batch_runs',
    )
    brief_override = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"BatchRun {self.id} ({self.tasks.count()} tasks)"


class NotificationPreference(models.Model):
    """Per-user notification preferences (Milestone 12.4). Auto-created with
    both channels on the first time preferences are read for a user."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notification_prefs',
    )
    in_app = models.BooleanField(default=True)
    email = models.BooleanField(default=True)

    def __str__(self):
        return f"prefs({self.user})"


class WebResearchSession(models.Model):
    """aria_web_research_session/1.0 (2C-2A-CORR-2) — one bounded, governed
    Web Research session. Statuses per §10; results live in WebSourceRecord
    rows + bounded JSON summaries; large bodies live in the quarantine dir."""
    STATUSES = [(s, s) for s in (
        "PLANNED", "SEARCHING", "FETCHING", "QUARANTINED",
        "AWAITING_HUMAN_REVIEW", "PARTIALLY_APPROVED", "APPROVED",
        "REJECTED", "BLOCKED", "FAILED_REVIEWABLE")]
    product_identity = models.CharField(max_length=200)
    candidate_id = models.CharField(max_length=60, blank=True, default="")
    modes = models.JSONField(default=list)          # requested discovery modes
    queries = models.JSONField(default=list)
    summary = models.JSONField(default=dict)        # counts/facts/conflicts/rights
    status = models.CharField(max_length=32, choices=STATUSES,
                              default="PLANNED")
    human_review_status = models.CharField(max_length=40, blank=True,
                                           default="UNREVIEWED")
    session_hash = models.CharField(max_length=64, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class WebSourceRecord(models.Model):
    """web_source_record/1.0 — one retrieved (or blocked) public source with
    full provenance. Rights + use permissions DEFAULT DENY (§14)."""
    session = models.ForeignKey(WebResearchSession, on_delete=models.CASCADE,
                                related_name="sources")
    original_url = models.TextField()
    resolved_url = models.TextField(blank=True, default="")
    domain = models.CharField(max_length=200, blank=True, default="")
    title = models.CharField(max_length=300, blank=True, default="")
    source_tier = models.PositiveSmallIntegerField(default=6)     # §3 tiers 1-6
    source_type = models.CharField(max_length=40, blank=True, default="")
    classification = models.CharField(max_length=40, blank=True,
                                      default="unknown")  # exact/analog/inspiration
    access_policy_result = models.CharField(max_length=60, blank=True,
                                            default="")
    robots_result = models.CharField(max_length=30, blank=True, default="")
    http_status = models.IntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=60, blank=True, default="")
    byte_count = models.PositiveIntegerField(default=0)
    content_sha256 = models.CharField(max_length=64, blank=True, default="")
    match_score = models.FloatField(default=0.0)
    rights_state = models.CharField(max_length=40, default="RIGHTS_UNKNOWN")
    licence_url = models.TextField(blank=True, default="")
    attribution_text = models.CharField(max_length=300, blank=True, default="")
    # §14 permissions — ALL default False; only bounded retrieval is implicit
    retrieval_permission = models.BooleanField(default=False)
    reference_view_permission = models.BooleanField(default=False)
    fact_source_permission = models.BooleanField(default=False)
    provider_input_permission = models.BooleanField(default=False)
    artwork_reuse_permission = models.BooleanField(default=False)
    design_memory_permission = models.BooleanField(default=False)
    human_review_state = models.CharField(max_length=40, default="UNREVIEWED")
    quarantine_path = models.CharField(max_length=400, blank=True, default="")
    extraction_warnings = models.JSONField(default=list)
    facts = models.JSONField(default=list)        # web_product_fact_candidate/1.0
    retrieved_at = models.DateTimeField(auto_now_add=True)


class WebAccessRecord(models.Model):
    """§24 web-access ledger — one row per search call / fetch / policy block.
    Distinct from ApiCallRecord (image/LLM providers)."""
    session = models.ForeignKey(WebResearchSession, on_delete=models.CASCADE,
                                related_name="accesses", null=True, blank=True)
    kind = models.CharField(max_length=30)          # search|page_fetch|image_fetch|policy_block
    url = models.TextField(blank=True, default="")
    domain = models.CharField(max_length=200, blank=True, default="")
    outcome = models.CharField(max_length=60, blank=True, default="")
    http_status = models.IntegerField(null=True, blank=True)
    byte_count = models.PositiveIntegerField(default=0)
    detail = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class PaletteIntentConfirmation(models.Model):
    """PALT-M4C-4 — a versioned record of what a human confirmed the engine
    understood from a selected design.

    Only ``HUMAN_CONFIRMED_DESIGN_INTENT`` is design authority, so this is
    the durable boundary between an AI reading and something allowed to
    drive geometry. Rows are append-only: a revision creates a NEW version
    rather than editing an old one, so the draft, every correction and the
    reasoning behind each stay separately auditable.
    """

    SCOPE_VISIBLE_COMPOSITION = "VISIBLE_COMPOSITION_ONLY"

    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE,
                             related_name="intent_confirmations")
    version = models.PositiveIntegerField(default=1)
    concept_reference = models.CharField(max_length=500)
    #: identity of the AI draft this confirmation was made against
    draft_identity = models.CharField(max_length=64)
    #: identity of the confirmation actions themselves
    confirmation_identity = models.CharField(max_length=64)
    #: identity of the resulting confirmed intent
    confirmed_intent_identity = models.CharField(max_length=64)
    panel = models.JSONField(default=dict)
    actions = models.JSONField(default=list)
    confirmed_intent = models.JSONField(default=dict)
    scope = models.CharField(max_length=64,
                             default=SCOPE_VISIBLE_COMPOSITION)
    superseded_by = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="supersedes")
    gate_decision = models.ForeignKey(
        GateDecision, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="intent_confirmations")
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="intent_confirmations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["task_id", "version"]
        unique_together = [("task", "version")]

    def __str__(self):
        return f"intent confirmation v{self.version} for task {self.task_id}"

    @property
    def is_current(self):
        return self.superseded_by_id is None


class PaletteMaterialArtifact(models.Model):
    """M5 §10 — the governed task artifact for one material variant.

    One row per (task, material contract) pair. This is the step between
    the Design Graph and the Blender scene that the workflow trace has to
    pass through: a variant that renders without a row here bypassed the
    governed path, and the trace reports exactly that.
    """

    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE,
                             related_name="material_artifacts")
    variant_name = models.CharField(max_length=80)
    #: identity chain — every link the trace must be able to follow
    intent_confirmation = models.ForeignKey(
        PaletteIntentConfirmation, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="material_artifacts")
    material_contract_identity = models.CharField(max_length=64)
    design_graph_identity = models.CharField(max_length=64)
    geometry_identity = models.CharField(max_length=64)
    scene_identity = models.CharField(max_length=64)
    render_identity = models.CharField(max_length=64)
    evidence_path = models.CharField(max_length=500)
    evidence_sha256 = models.CharField(max_length=64)
    review_board_artifact_identity = models.CharField(max_length=64,
                                                      blank=True)
    material_contract = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("task", "variant_name")]
        ordering = ["task_id", "variant_name"]

    def __str__(self):
        return f"material artifact {self.variant_name} (task {self.task_id})"


class InspirationReading(models.Model):
    """§BH69(2): what the vision model read from ONE inspiration picture — layout, colours (measured from its pixels),
    mood, finish, type style, what a design should take, and apart from all of it what it saw and must never take (a
    brand's name, a logo, the words on it). Keyed by the picture's sha256, so a picture is read once however often it
    is dropped. The picture's bytes are read here and go nowhere else (apps/pipeline/services/inspiration.py)."""
    sha256 = models.CharField(max_length=64, unique=True)
    reading = models.JSONField(default=dict)
    model = models.CharField(max_length=80, blank=True, default="")
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    api_call = models.ForeignKey(ApiCallRecord, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="inspiration_readings")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="inspiration_readings")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"inspiration reading {self.sha256[:12]}"


class LearnedShape(models.Model):
    """§BH71 PART 3, the owner's goal of 2026-09-28: "When a concept shows a shape the system doesn't know, it says so
    and offers to learn it." A lid shape the system learned at a person's word, from an approved concept whose own
    traced outline shows it — never from a brief's words alone — one per form and kind; from then on a variant of its
    form at every design's shape step (apps/pipeline/services/learned_shapes.py). Its geometry is the kind's own
    (an oval is an ellipse in the size a person confirms) and the aspect its picture showed, as seen."""
    form = models.CharField(max_length=32)
    kind = models.CharField(max_length=32)
    label = models.CharField(max_length=80)
    geometry = models.JSONField(default=dict)
    source_task = models.ForeignKey(DesignTask, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="learned_shapes")
    source_sha256 = models.CharField(max_length=64)
    learned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="learned_shapes")
    learned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["form", "kind"], name="learned_shape_one_per_form_and_kind")]

    def __str__(self):
        return f"learned {self.form} {self.kind}"


class TrendBoard(models.Model):
    """§BH71 PART 2, the owner's goal of 2026-09-28: "For every new design, search across platforms (Pinterest, Behance,
    Dribbble, Instagram, packaging sites like The Dieline and Packaging of the World) for current trends in that
    product type. Show the found pictures on the design page before directions. They are used by default; I can untick
    any I dislike in one click." One board per design: the searches it made (its session), what each platform
    refused and why, the pictures and link cards it found (TrendPick), and when and how it was confirmed — by his
    click, by the window closing, by a batch run, or because nothing was found — with the ticked pictures as they
    stood at that moment (apps/pipeline/services/trend_board.py)."""
    BUILDING, READY, CONFIRMED, FAILED = "BUILDING", "READY", "CONFIRMED", "FAILED"
    STATUSES = [(s, s) for s in (BUILDING, READY, CONFIRMED, FAILED)]
    task = models.OneToOneField(DesignTask, on_delete=models.CASCADE, related_name="trend_board")
    session = models.ForeignKey(WebResearchSession, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="trend_boards")
    status = models.CharField(max_length=16, choices=STATUSES, default=BUILDING)
    #: why a board failed, by the exception's type — never its message (a provider error can echo the request)
    failure = models.CharField(max_length=120, blank=True, default="")
    subject = models.CharField(max_length=160, blank=True, default="")
    #: [{"platform", "query", "scope", "credits", "results"}] — every search it made, in order ("report the queries")
    searches = models.JSONField(default=list, blank=True)
    #: {platform: {"mode", "words", "robots": {host: verdict}}} — what each platform refused and why
    refusals = models.JSONField(default=dict, blank=True)
    #: the moment the pictures stop taking unticks unless he presses on first
    review_deadline = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="trend_boards_confirmed")
    confirmed_how = models.CharField(max_length=40, blank=True, default="")
    #: the picks ticked when it was confirmed — what the directions were made with
    used_at_confirm = models.JSONField(default=list, blank=True)
    #: [his goal for the pitch, 2026-10-15, A (1)] the written trend brief — its points by section, its sources linked
    #: (trend_board.write_brief); {} until it is written
    brief = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"trend board of task {self.task_id} ({self.status})"


class TrendPick(models.Model):
    """One thing a trend board found: a PICTURE — fetched under every guard into quarantine, read into words, ticked
    by default and unticked in one click — or a LINK card, a page on a platform whose pictures are not fetched (its
    robots.txt refuses, or its terms forbid automated collection), shown with its link and never ticked, because it
    feeds nothing. A picture's bytes stay in quarantine and reach one model call, the read; its words are the
    InspirationReading its sha256 names."""
    PICTURE, LINK = "picture", "link"
    KINDS = [(PICTURE, PICTURE), (LINK, LINK)]
    board = models.ForeignKey(TrendBoard, on_delete=models.CASCADE, related_name="picks")
    number = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=10, choices=KINDS)
    platform = models.CharField(max_length=40)
    page_url = models.TextField(blank=True, default="")
    image_url = models.TextField(blank=True, default="")
    #: shown on the board only — a title carries brand names, so it never reaches the planner
    title = models.CharField(max_length=300, blank=True, default="")
    source = models.ForeignKey(WebSourceRecord, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="trend_picks")
    sha256 = models.CharField(max_length=64, blank=True, default="", db_index=True)
    thumb_path = models.CharField(max_length=400, blank=True, default="")
    thumb_width = models.PositiveIntegerField(default=0)
    thumb_height = models.PositiveIntegerField(default=0)
    #: why a picture feeds nothing (not read: the day's cap, no key, a picture that would not open) — "" when it feeds
    unread_reason = models.CharField(max_length=200, blank=True, default="")
    used = models.BooleanField(default=False)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="trend_picks_changed")
    changed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["board", "number"], name="trend_pick_one_number_per_board")]

    def __str__(self):
        return f"trend pick {self.number} of board {self.board_id} ({self.kind})"


class Round(models.Model):
    """One owner-started, product-independent whole-object creative round."""
    slug = models.SlugField(max_length=100, unique=True)
    request_key = models.CharField(max_length=64, unique=True)
    product = models.ForeignKey('core.Product', null=True, blank=True, on_delete=models.SET_NULL)
    product_brief = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='creative_rounds')
    state = models.CharField(max_length=24, default='queued', db_index=True)
    current_step = models.CharField(max_length=24, default='seeds')
    artifacts = models.JSONField(default=dict, blank=True)
    marks = models.JSONField(default=dict, blank=True)
    pick = models.JSONField(default=dict, blank=True)
    marks_due_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    budget_usd = models.DecimalField(max_digits=6, decimal_places=2, default=22)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class RoundStep(models.Model):
    """Durable queue identity; redelivery resumes saved calls, never repurchases them."""
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='steps')
    name = models.CharField(max_length=24)
    position = models.PositiveSmallIntegerField()
    state = models.CharField(max_length=16, default='queued', db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    dispatches = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    history = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position']
        constraints = [models.UniqueConstraint(fields=['round', 'name'], name='round_step_identity')]


class RoundMaster(models.Model):
    """Independent day-two outbox; the completed pick and day-one spend stay immutable."""
    round = models.OneToOneField(Round, on_delete=models.CASCADE, related_name='master_build')
    state = models.CharField(max_length=16, default='queued', db_index=True)
    current_step = models.CharField(max_length=24, default='panels')
    steps = models.JSONField(default=dict)
    inputs = models.JSONField(default=dict)
    publication = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    budget_usd = models.DecimalField(max_digits=6, decimal_places=2, default=15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
