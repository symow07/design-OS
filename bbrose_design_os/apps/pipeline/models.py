from django.db import models

TASK_STATUS = [
    ('queued', 'Queued'),
    ('running', 'Running'),
    ('awaiting_gate_1', 'Awaiting Gate 1'),
    ('gate_1_approved', 'Gate 1 Approved'),
    ('awaiting_dimensions', 'Awaiting Dimension Confirmation'),
    ('generating_dieline', 'Generating Dieline'),
    ('awaiting_gate_2', 'Awaiting Gate 2'),
    ('gate_2_approved', 'Gate 2 Approved'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
    ('rejected', 'Rejected'),
]


class DesignTask(models.Model):
    brand = models.ForeignKey('core.Brand', on_delete=models.CASCADE)
    product = models.ForeignKey('core.Product', null=True, blank=True, on_delete=models.SET_NULL)
    campaign = models.ForeignKey('core.Campaign', null=True, blank=True, on_delete=models.SET_NULL)
    task_text = models.TextField()  # what you typed
    status = models.CharField(max_length=50, choices=TASK_STATUS, default='queued')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    gate_1_notes = models.TextField(blank=True)  # your feedback if rejected
    gate_2_notes = models.TextField(blank=True)


class AgentLog(models.Model):
    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE, related_name='logs')
    agent_name = models.CharField(max_length=100)  # ARIA, CreativeDirector, etc.
    action = models.TextField()  # human-readable: "Retrieved 4 similar products"
    payload = models.JSONField(null=True, blank=True)  # raw data
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=20, default='info')  # info, warning, error


class CreativeBrief(models.Model):
    task = models.OneToOneField(DesignTask, on_delete=models.CASCADE, related_name='brief')
    retrieved_products = models.JSONField(default=list)  # similar products found
    retrieved_references = models.JSONField(default=list)
    directions = models.JSONField()  # list of 3-5 direction objects
    # each direction: {name, rationale, palette, material, finish, prompt_seed}
    created_at = models.DateTimeField(auto_now_add=True)


class GeneratedImage(models.Model):
    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE, related_name='images')
    direction_name = models.CharField(max_length=200)
    prompt_used = models.TextField()
    image_url = models.URLField(max_length=500)
    image_file = models.ImageField(upload_to='generated/', blank=True)
    variation_number = models.IntegerField(default=1)  # 1, 2, or 3
    qa_passed = models.BooleanField(default=False)
    qa_notes = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class PackagingOutput(models.Model):
    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE, related_name='packaging_outputs')
    approved_image = models.ForeignKey(GeneratedImage, on_delete=models.CASCADE)
    spec_sheet = models.JSONField()  # {structure, dimensions, material, finish, color_codes}
    pacdora_render_url = models.URLField(blank=True)
    dieline_file = models.FileField(upload_to='dielines/', blank=True)  # SVG (dieline backend)
    dieline_ai_file = models.FileField(upload_to='dielines/', blank=True)  # Illustrator .ai (best-effort)
    dieline_job = models.ForeignKey(
        'dielines.DielineJob', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='packaging_outputs',
    )
    spec_pdf = models.FileField(upload_to='spec_sheets/', blank=True)
    is_final_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
