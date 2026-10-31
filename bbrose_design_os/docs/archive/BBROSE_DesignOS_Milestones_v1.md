# BBROSE Design OS — Complete Build Milestones
**Stack:** Python · Django · PostgreSQL · Claude API · OpenAI API · Pacdora API · HTML/CSS/JS  
**Architecture:** ARIA lead agent + 4 sub-agents · Admin dashboard · Approval gates  
**Scope:** Solo first (you only) → expand to team later

---

## How to use this document

Each milestone is a self-contained Claude Code prompt.  
Copy the prompt → paste into Claude Code → execute → verify → move to next.  
Do NOT skip milestones. Each one builds on the last.  
Every prompt assumes your working directory is `bbrose_design_os/`.

---

## PHASE 0 — Project Foundation
**Goal:** Django project running locally, PostgreSQL connected, environment configured.

---

### Milestone 0.1 — Project Scaffold

```
Create a new Django 4.2 project called bbrose_design_os.

Structure:
bbrose_design_os/
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── core/          ← brand data, products, campaigns
│   ├── pipeline/      ← design requests, agents, outputs
│   ├── dashboard/     ← views for admin UI
│   └── accounts/      ← user auth (just me for now)
├── templates/
├── static/
├── .env
├── .env.example
├── requirements.txt
└── manage.py

requirements.txt must include:
django==4.2
psycopg2-binary
python-dotenv
anthropic
openai
requests
pillow
django-environ
whitenoise
celery
redis

settings.py must:
- Load all secrets from .env using django-environ
- Use PostgreSQL as the database
- Have STATIC_ROOT configured
- Have MEDIA_ROOT configured for uploaded/generated assets
- Have INSTALLED_APPS include all four apps

.env.example must include:
SECRET_KEY=
DEBUG=True
DATABASE_URL=postgresql://user:password@localhost:5432/bbrose_db
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
PACDORA_API_KEY=
REDIS_URL=redis://localhost:6379/0
MEDIA_ROOT=media/
```

---

### Milestone 0.2 — Database Setup

```
Create the PostgreSQL database and run initial Django setup.

Tasks:
1. Create database: bbrose_db
2. Run: python manage.py migrate
3. Run: python manage.py createsuperuser
4. Verify Django admin loads at /admin/
5. Confirm database connection is working

No models yet. Just confirm the foundation is solid.
```

---

## PHASE 1 — Core Data Models
**Goal:** Brand intelligence lives in PostgreSQL. ARIA can query it.

---

### Milestone 1.1 — Brand Core Models

```
In apps/core/models.py, create these models exactly:

class Brand(models.Model):
    name = models.CharField(max_length=200)
    master_brief = models.TextField()  # BBROSE master brand brief
    positioning = models.TextField(blank=True)
    what_we_are_not = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ColorSystem(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='color_systems')
    name = models.CharField(max_length=200)  # e.g. "Blush Core"
    system_id = models.CharField(max_length=20)  # e.g. "CS-001"
    palette = models.JSONField()  # list of {role, name, hex, pantone, usage}
    material_pairings_approved = models.JSONField(default=list)
    material_pairings_rejected = models.JSONField(default=list)
    image_generation_context = models.TextField()  # prompt seed for this palette
    status = models.CharField(max_length=50, default='canonical')

class MaterialSystem(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='material_systems')
    name = models.CharField(max_length=200)
    material_id = models.CharField(max_length=20)  # e.g. "ML-001"
    properties = models.JSONField()
    finish_combinations = models.JSONField(default=list)
    prompt_descriptors = models.TextField()
    categories_used_in = models.JSONField(default=list)
    status = models.CharField(max_length=50, default='approved')

class AestheticLanguage(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='aesthetic_language')
    name = models.CharField(max_length=200)
    aesthetic_id = models.CharField(max_length=20)  # e.g. "AL-001"
    core_description = models.TextField()
    prompt_seed_product = models.TextField()  # for product photography
    prompt_seed_campaign = models.TextField()  # for campaign visuals
    what_breaks_this = models.JSONField(default=list)
    status = models.CharField(max_length=50, default='canonical')

class PackagingStructure(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='packaging_structures')
    name = models.CharField(max_length=200)
    structure_id = models.CharField(max_length=20)  # e.g. "PKG-STR-001"
    structure_type = models.CharField(max_length=100)  # tube, carton, bottle, etc.
    dimensions = models.JSONField()  # {diameter, height, units}
    printable_surface = models.JSONField()  # {width, height, aspect_ratio}
    surface_zones = models.JSONField()  # {logo_zone, texture_zone, accent_zone}
    pacdora_template_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=50, default='active')

Register all models in admin.py.
Run makemigrations and migrate.
```

---

### Milestone 1.2 — Product and Campaign Models

```
In apps/core/models.py, add:

PRODUCT_CATEGORIES = [
    ('SK', 'Skincare'),
    ('HC', 'Hair Care'),
    ('CO', 'Cosmetics'),
]

PRODUCT_STATUS = [
    ('active', 'Active'),
    ('in_development', 'In Development'),
    ('archived', 'Archived'),
    ('rejected', 'Rejected'),
]

class Product(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    product_id = models.CharField(max_length=50, unique=True)  # from Excel e.g. "BBR-CO-042"
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=2, choices=PRODUCT_CATEGORIES)
    year = models.IntegerField()  # 2025 or 2026
    status = models.CharField(max_length=50, choices=PRODUCT_STATUS, default='active')
    color_system = models.ForeignKey(ColorSystem, null=True, blank=True, on_delete=models.SET_NULL)
    packaging_structure = models.ForeignKey(PackagingStructure, null=True, blank=True, on_delete=models.SET_NULL)
    material = models.ForeignKey(MaterialSystem, null=True, blank=True, on_delete=models.SET_NULL)
    dimensions = models.CharField(max_length=200, blank=True)
    finish_notes = models.TextField(blank=True)
    product_image = models.ImageField(upload_to='products/', blank=True)  # the PNG from Excel
    packaging_image = models.ImageField(upload_to='packaging/', blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Campaign(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='campaigns')
    name = models.CharField(max_length=200)
    direction = models.TextField()
    aesthetic_notes = models.TextField(blank=True)
    status = models.CharField(max_length=50, default='active')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

Run makemigrations and migrate.
Register in admin with list_display, list_filter, search_fields.
```

---

### Milestone 1.3 — Brand Data Seed

```
Create a Django management command: apps/core/management/commands/seed_bbrose.py

This command seeds the database with BBROSE's initial brand data:

Brand:
  name: "BBROSE"
  master_brief: [full BBROSE master brief text — feminine luxury beauty brand,
  soft premium aesthetic, blush pink / nude / warm cream palette, editorial 
  beauty direction, luxury cosmetic packaging, glossy + matte material contrast,
  rose gold details, soft cinematic branding, elegant but modern, minimal but 
  not empty, premium beauty-store aesthetic]

ColorSystem CS-001 "Blush Core":
  palette: [
    {role: "Primary", name: "Blush", hex: "#F2C4CE", pantone: "698 C", usage: "Main surfaces, hero cartons"},
    {role: "Secondary", name: "Pale Petal", hex: "#F7DDE3", pantone: "698 lighter", usage: "Interior, secondary panels"},
    {role: "Accent", name: "Deep Rose", hex: "#8B3A52", pantone: "209 C", usage: "Typography, fine detail lines"},
    {role: "Metallic", name: "Rose Gold", hex: "Metallic 10122 C", usage: "Caps, closures, foil detail"},
    {role: "Ground", name: "Warm Cream", hex: "#FAF3EC", pantone: "9182 C", usage: "Base packaging, backgrounds"}
  ]
  image_generation_context: "blush pink nude palette, warm cream surface, 
  rose gold metallic accents, soft feminine luxury, warm light, #F2C4CE primary"

ColorSystem CS-002 "Nude Warm":
  [create appropriate data]

AestheticLanguage AL-001 "Soft Luxury":
  prompt_seed_product: "soft luxury beauty product photography, warm diffused 
  lighting, blush pink and warm cream palette, silk surface texture, rose gold 
  metallic detail, shallow depth of field, editorial beauty aesthetic, magazine 
  quality, feminine premium cosmetics, warm ambient light"
  prompt_seed_campaign: "luxury beauty campaign, soft cinematic light, warm skin 
  tones, blush pink editorial beauty, intimate close-up, silk and soft textures,
  high fashion beauty photography aesthetic, feminine and editorial, premium 
  cosmetic brand campaign visual"
  what_breaks_this: ["hard shadows", "cool/blue tones", "white background", 
  "commercial feel", "flat lighting"]

MaterialSystem ML-001 "Glossy Acrylic":
  prompt_descriptors: "glossy acrylic packaging, mirror finish, high-gloss 
  surface, luxury cosmetic packaging, reflective premium finish"
  categories_used_in: ["CO"]

PackagingStructure PKG-STR-001 "Lip Oil Roller":
  structure_type: "cylindrical tube"
  dimensions: {diameter: "11mm", height: "82mm", units: "mm"}
  printable_surface: {width: "34.6mm", height: "82mm", aspect_ratio: "9:21"}
  surface_zones: {
    logo_zone: "upper 30% — clear, no texture",
    texture_zone: "lower 60% — primary graphic surface",
    accent_line: "80% height horizontal band"
  }

Run: python manage.py seed_bbrose
Verify all records created in Django admin.
```

---

## PHASE 2 — Pipeline Models
**Goal:** The design request, agent activity, and output are all tracked in the database.

---

### Milestone 2.1 — Pipeline Models

```
In apps/pipeline/models.py, create:

TASK_STATUS = [
    ('queued', 'Queued'),
    ('running', 'Running'),
    ('awaiting_gate_1', 'Awaiting Gate 1'),
    ('gate_1_approved', 'Gate 1 Approved'),
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
    dieline_file = models.FileField(upload_to='dielines/', blank=True)
    is_final_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

Run makemigrations and migrate.
Register all in admin.
```

---

## PHASE 3 — ARIA and Sub-Agents
**Goal:** The full agent system is wired up and runs end-to-end.

---

### Milestone 3.1 — Claude Service Layer

```
Create apps/pipeline/services/claude_service.py

This is the base service all agents use to call Claude API.

import anthropic
from django.conf import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

def call_claude(system_prompt, user_message, tools=None, max_tokens=4096):
    """
    Base Claude API call used by all agents.
    Returns the full response object.
    """
    kwargs = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}]
    }
    if tools:
        kwargs["tools"] = tools
    
    response = client.messages.create(**kwargs)
    return response

def extract_text(response):
    """Extract plain text from Claude response."""
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""

def extract_tool_use(response):
    """Extract tool use calls from Claude response."""
    calls = []
    for block in response.content:
        if block.type == "tool_use":
            calls.append({"name": block.name, "input": block.input})
    return calls

Write a test at the bottom:
if __name__ == "__main__":
    response = call_claude(
        system_prompt="You are a helpful assistant.",
        user_message="Say hello in one sentence."
    )
    print(extract_text(response))
```

---

### Milestone 3.2 — Brand Context Retriever

```
Create apps/pipeline/services/brand_context.py

This module retrieves brand intelligence from PostgreSQL and formats it
as a structured context string that ARIA injects into every agent call.

from apps.core.models import Brand, Product, ColorSystem, MaterialSystem, AestheticLanguage, PackagingStructure

def build_brand_context(brand_id, category=None):
    """
    Builds a complete brand context string for injection into agent system prompts.
    """
    brand = Brand.objects.get(id=brand_id)
    
    context = f"""
## BBROSE Brand Master Brief
{brand.master_brief}

## What BBROSE Is Not
{brand.what_we_are_not}

## Canonical Color Systems
"""
    for cs in brand.color_systems.filter(status='canonical'):
        context += f"\n### {cs.system_id} — {cs.name}\n"
        context += f"Palette: {cs.palette}\n"
        context += f"Image generation context: {cs.image_generation_context}\n"

    context += "\n## Aesthetic Language\n"
    for al in brand.aesthetic_language.filter(status='canonical'):
        context += f"\n### {al.aesthetic_id} — {al.name}\n"
        context += f"{al.core_description}\n"
        context += f"Product prompt seed: {al.prompt_seed_product}\n"

    context += "\n## Material Language\n"
    for ml in brand.material_systems.filter(status='approved'):
        context += f"\n### {ml.material_id} — {ml.name}\n"
        context += f"Prompt descriptors: {ml.prompt_descriptors}\n"

    return context

def find_similar_products(brand_id, category, task_text, limit=5):
    """
    Finds similar products from the database relevant to the current task.
    Simple keyword match for Phase 1 — upgrade to vector search in Phase 2.
    """
    products = Product.objects.filter(
        brand_id=brand_id,
        status='active'
    )
    if category:
        products = products.filter(category=category)
    return list(products.values(
        'product_id', 'name', 'category', 'year',
        'finish_notes', 'notes'
    )[:limit])

def get_packaging_structure(structure_id):
    """Returns packaging structure data for prompt construction."""
    try:
        s = PackagingStructure.objects.get(structure_id=structure_id)
        return {
            'name': s.name,
            'type': s.structure_type,
            'dimensions': s.dimensions,
            'printable_surface': s.printable_surface,
            'surface_zones': s.surface_zones,
            'pacdora_template_id': s.pacdora_template_id,
        }
    except PackagingStructure.DoesNotExist:
        return None
```

---

### Milestone 3.3 — Creative Director Sub-Agent

```
Create apps/pipeline/agents/creative_director.py

from apps.pipeline.services.claude_service import call_claude, extract_text
from apps.pipeline.services.brand_context import build_brand_context, find_similar_products
import json

CREATIVE_DIRECTOR_SYSTEM = """
You are the Creative Director for BBROSE, a luxury beauty brand.

Your job is to analyze a design task and produce 3-5 distinct design directions.

Each direction must:
1. Have a unique name (poetic, brand-appropriate)
2. Include a rationale grounded in BBROSE brand history
3. Specify exact palette (which color system, which swatches)
4. Specify material and finish combination
5. Explain how it connects to or evolves from past BBROSE products
6. Be genuinely different from the other directions

You never produce generic beauty aesthetics.
Every direction must feel like it belongs to BBROSE specifically.

Respond ONLY with valid JSON in this exact format:
{
  "directions": [
    {
      "name": "Direction name",
      "rationale": "Why this direction, connected to brand history",
      "palette": "Which color system and specific swatches",
      "material": "Material and finish specification",
      "finish_combination": "Exact finish pairing",
      "connected_to": "Which past product or concept this evolves from",
      "prompt_seed": "Initial image generation direction (2-3 sentences)"
    }
  ]
}
"""

class CreativeDirectorAgent:
    
    def __init__(self, task, brand_id, log_fn=None):
        self.task = task
        self.brand_id = brand_id
        self.log = log_fn or (lambda msg, data=None: None)
    
    def run(self):
        self.log("Creative Director: retrieving brand context")
        brand_context = build_brand_context(self.brand_id)
        
        self.log("Creative Director: finding similar products")
        similar = find_similar_products(self.brand_id, None, self.task.task_text)
        similar_text = json.dumps(similar, indent=2)
        
        user_message = f"""
## Task
{self.task.task_text}

## Brand Context
{brand_context}

## Similar BBROSE Products for Reference
{similar_text}

Generate 3-5 design directions for this task.
"""
        
        self.log("Creative Director: generating design directions")
        response = call_claude(CREATIVE_DIRECTOR_SYSTEM, user_message, max_tokens=3000)
        
        try:
            result = json.loads(extract_text(response))
            self.log(f"Creative Director: produced {len(result['directions'])} directions")
            return result['directions']
        except json.JSONDecodeError:
            self.log("Creative Director: JSON parse error", level='error')
            return []
```

---

### Milestone 3.4 — Prompt Engineer Sub-Agent

```
Create apps/pipeline/agents/prompt_engineer.py

from apps.pipeline.services.claude_service import call_claude, extract_text
from apps.pipeline.services.brand_context import get_packaging_structure
import json

PROMPT_ENGINEER_SYSTEM = """
You are the Prompt Engineer for BBROSE, a luxury beauty brand.

Your job is to transform a creative direction into a precise, 
dieline-aware image generation prompt.

A dieline-aware prompt must:
1. Specify the exact aspect ratio matching the packaging structure's printable surface
2. Define surface zones — where logo goes, where texture goes, where accent lines go
3. Use "flat graphic design" or "flat surface artwork" — NOT "product photography"
4. Anchor the palette with specific hex codes
5. Include the AL-001 Soft Luxury aesthetic seed
6. Specify "no photography, flat graphic, works as cylinder wrap" for tube structures
7. End with the correct --ar flag for Midjourney or aspect_ratio for DALL-E

Respond ONLY with valid JSON:
{
  "prompts": [
    {
      "direction_name": "Name from creative direction",
      "full_prompt": "Complete image generation prompt",
      "aspect_ratio": "9:21",
      "notes": "Any special instructions for this prompt"
    }
  ]
}
"""

class PromptEngineerAgent:
    
    def __init__(self, directions, packaging_structure_id, log_fn=None):
        self.directions = directions
        self.structure = get_packaging_structure(packaging_structure_id) if packaging_structure_id else None
        self.log = log_fn or (lambda msg, data=None: None)
    
    def run(self):
        self.log("Prompt Engineer: building dieline-aware prompts")
        
        structure_text = json.dumps(self.structure, indent=2) if self.structure else "No structure specified — use standard beauty product proportions"
        directions_text = json.dumps(self.directions, indent=2)
        
        user_message = f"""
## Creative Directions
{directions_text}

## Packaging Structure
{structure_text}

Build one dieline-aware image generation prompt per direction.
"""
        
        response = call_claude(PROMPT_ENGINEER_SYSTEM, user_message, max_tokens=3000)
        
        try:
            result = json.loads(extract_text(response))
            self.log(f"Prompt Engineer: built {len(result['prompts'])} prompts")
            return result['prompts']
        except json.JSONDecodeError:
            self.log("Prompt Engineer: JSON parse error", level='error')
            return []
```

---

### Milestone 3.5 — Image Producer Sub-Agent

```
Create apps/pipeline/agents/image_producer.py

import openai
import requests
import os
from django.conf import settings
from django.core.files.base import ContentFile
from apps.pipeline.models import GeneratedImage

openai.api_key = settings.OPENAI_API_KEY

class ImageProducerAgent:
    
    def __init__(self, task, prompts, log_fn=None):
        self.task = task
        self.prompts = prompts
        self.log = log_fn or (lambda msg, data=None: None)
    
    def run(self):
        generated = []
        
        for i, prompt_data in enumerate(self.prompts):
            self.log(f"Image Producer: generating image {i+1} of {len(self.prompts)}")
            
            try:
                response = openai.images.generate(
                    model="dall-e-3",
                    prompt=prompt_data['full_prompt'],
                    size="1024x1792",  # portrait — closest to most packaging aspect ratios
                    quality="hd",
                    n=1
                )
                
                image_url = response.data[0].url
                
                # Save to database
                img = GeneratedImage.objects.create(
                    task=self.task,
                    direction_name=prompt_data['direction_name'],
                    prompt_used=prompt_data['full_prompt'],
                    image_url=image_url,
                    variation_number=i + 1,
                )
                
                # Download and save file locally
                img_response = requests.get(image_url)
                if img_response.status_code == 200:
                    img.image_file.save(
                        f"task_{self.task.id}_var_{i+1}.png",
                        ContentFile(img_response.content)
                    )
                
                generated.append(img)
                self.log(f"Image Producer: saved variation {i+1}")
                
            except Exception as e:
                self.log(f"Image Producer: failed on variation {i+1} — {str(e)}", level='error')
        
        return generated
```

---

### Milestone 3.6 — QA Reviewer Sub-Agent

```
Create apps/pipeline/agents/qa_reviewer.py

from apps.pipeline.services.claude_service import call_claude, extract_text
from apps.pipeline.services.brand_context import build_brand_context
import json

QA_REVIEWER_SYSTEM = """
You are the QA Reviewer for BBROSE, a luxury beauty brand.

Your job is to review generated images against BBROSE brand standards
and flag any issues before they reach the approval stage.

Check each image description against:
1. Palette — does it use BBROSE colors (blush pink, nude warm, warm cream, rose gold)?
2. Aesthetic — does it match soft luxury, editorial beauty direction?
3. Finish — does it respect glossy/matte contrast rules?
4. Category rules — glossy for cosmetics, frosted/matte for skincare?
5. What BBROSE is NOT — not clinical white/silver, not cold, not masculine

Be honest. Flag real issues. Don't rubber-stamp bad outputs.

Respond ONLY with valid JSON:
{
  "reviews": [
    {
      "image_id": "database ID",
      "passed": true or false,
      "score": 1-10,
      "issues": ["list of specific issues if any"],
      "recommendation": "approve / revise with notes / reject"
    }
  ]
}
"""

class QAReviewerAgent:
    
    def __init__(self, images, brand_id, log_fn=None):
        self.images = images
        self.brand_id = brand_id
        self.log = log_fn or (lambda msg, data=None: None)
    
    def run(self):
        self.log("QA Reviewer: checking brand compliance")
        brand_context = build_brand_context(self.brand_id)
        
        images_data = []
        for img in self.images:
            images_data.append({
                "id": img.id,
                "direction_name": img.direction_name,
                "prompt_used": img.prompt_used,
                "url": img.image_url
            })
        
        user_message = f"""
## Brand Standards
{brand_context}

## Images to Review
{json.dumps(images_data, indent=2)}

Review each image for brand compliance.
"""
        
        response = call_claude(QA_REVIEWER_SYSTEM, user_message, max_tokens=2000)
        
        try:
            result = json.loads(extract_text(response))
            
            # Update database with QA results
            for review in result['reviews']:
                img = next((i for i in self.images if i.id == review['image_id']), None)
                if img:
                    img.qa_passed = review['passed']
                    img.qa_notes = json.dumps(review)
                    img.save()
            
            passed = sum(1 for r in result['reviews'] if r['passed'])
            self.log(f"QA Reviewer: {passed}/{len(result['reviews'])} images passed")
            return result['reviews']
            
        except json.JSONDecodeError:
            self.log("QA Reviewer: JSON parse error", level='error')
            return []
```

---

### Milestone 3.7 — ARIA Lead Agent

```
Create apps/pipeline/agents/aria.py

This is the orchestrator. ARIA runs the full pipeline and pauses at gates.

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
                log_fn=lambda msg, data=None: self.log(msg, data, agent='CreativeDirector')
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
                log_fn=lambda msg, data=None: self.log(msg, data, agent='PromptEngineer')
            )
            prompts = pe_agent.run()
            
            # STAGE 3: Image Producer
            self.log("ARIA: delegating to Image Producer", agent='ARIA')
            ip_agent = ImageProducerAgent(
                self.task, prompts,
                log_fn=lambda msg, data=None: self.log(msg, data, agent='ImageProducer')
            )
            images = ip_agent.run()
            
            if not images:
                self._fail("Image Producer generated no images")
                return
            
            # STAGE 4: QA Reviewer
            self.log("ARIA: delegating to QA Reviewer", agent='ARIA')
            qa_agent = QAReviewerAgent(
                images, self.brand_id,
                log_fn=lambda msg, data=None: self.log(msg, data, agent='QAReviewer')
            )
            qa_results = qa_agent.run()
            
            # Save brief to database
            CreativeBrief.objects.create(
                task=self.task,
                directions=directions,
            )
            
            # GATE 1 — pause for human decision
            self.task.status = 'awaiting_gate_1'
            self.task.save()
            self.log("ARIA: reached Gate 1 — awaiting your approval")
            
        except Exception as e:
            self._fail(str(e))
    
    def resume_after_gate_1(self, approved_image_id):
        """Called when you approve an image at Gate 1."""
        from apps.pipeline.agents.pacdora_agent import PacdoraAgent
        from apps.pipeline.models import GeneratedImage
        
        image = GeneratedImage.objects.get(id=approved_image_id)
        image.is_approved = True
        image.save()
        
        self.task.status = 'gate_1_approved'
        self.task.save()
        self.log(f"ARIA: Gate 1 approved — image {approved_image_id}")
        
        # Build spec and call Pacdora
        pacdora_agent = PacdoraAgent(
            self.task, image,
            log_fn=lambda msg, data=None: self.log(msg, data, agent='Pacdora')
        )
        pacdora_agent.run()
        
        # Gate 2
        self.task.status = 'awaiting_gate_2'
        self.task.save()
        self.log("ARIA: reached Gate 2 — awaiting 3D mockup approval")
    
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
        self.task.status = 'failed'
        self.task.save()
        self.log(f"ARIA: pipeline failed — {reason}", level='error')
```

---

### Milestone 3.8 — Pacdora Agent

```
Create apps/pipeline/agents/pacdora_agent.py

import requests
from django.conf import settings
from apps.pipeline.models import PackagingOutput

class PacdoraAgent:
    
    def __init__(self, task, approved_image, log_fn=None):
        self.task = task
        self.image = approved_image
        self.log = log_fn or (lambda msg, data=None: None)
        self.api_key = settings.PACDORA_API_KEY
    
    def build_spec_sheet(self):
        """Build the handoff spec from task and product data."""
        product = self.task.product
        spec = {
            "product_name": product.name if product else "Unknown",
            "product_id": product.product_id if product else "N/A",
            "approved_image_url": self.image.image_url,
            "direction_name": self.image.direction_name,
        }
        
        if product and product.packaging_structure:
            s = product.packaging_structure
            spec.update({
                "structure_type": s.structure_type,
                "dimensions": s.dimensions,
                "printable_surface": s.printable_surface,
                "surface_zones": s.surface_zones,
                "pacdora_template_id": s.pacdora_template_id,
            })
        
        if product and product.color_system:
            spec["color_codes"] = product.color_system.palette
        
        if product and product.material:
            spec["material"] = product.material.name
            spec["prompt_descriptors"] = product.material.prompt_descriptors
        
        return spec
    
    def run(self):
        self.log("Pacdora: building spec sheet")
        spec = self.build_spec_sheet()
        
        # Save output record immediately with spec
        output = PackagingOutput.objects.create(
            task=self.task,
            approved_image=self.image,
            spec_sheet=spec,
        )
        
        # Attempt Pacdora API call
        # NOTE: Replace with actual Pacdora API endpoint once documented
        if self.api_key and self.api_key != "your_pacdora_api_key":
            try:
                self.log("Pacdora: calling API")
                response = requests.post(
                    "https://api.pacdora.com/v1/render",  # placeholder
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "template_id": spec.get("pacdora_template_id", ""),
                        "artwork_url": self.image.image_url,
                        "dimensions": spec.get("dimensions", {}),
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    output.pacdora_render_url = data.get("render_url", "")
                    output.save()
                    self.log(f"Pacdora: render received")
                else:
                    self.log(f"Pacdora API returned {response.status_code}", level='warning')
                    
            except Exception as e:
                self.log(f"Pacdora API error: {str(e)} — spec saved, manual handoff available", level='warning')
        else:
            self.log("Pacdora: no API key — spec saved for manual handoff")
        
        return output
```

---

## PHASE 4 — API Endpoints
**Goal:** Dashboard can trigger ARIA and receive real-time updates.

---

### Milestone 4.1 — Task and Pipeline Endpoints

```
Create apps/pipeline/views.py with these endpoints:

POST /api/tasks/create/
  Body: {task_text, product_id (optional), campaign_id (optional)}
  Action: creates DesignTask, triggers ARIAAgent.run() via Celery task
  Returns: {task_id, status}

GET /api/tasks/{task_id}/status/
  Returns: {status, logs (last 20), images (if gate_1), packaging_output (if gate_2)}

POST /api/tasks/{task_id}/gate1_approve/
  Body: {image_id}
  Action: calls aria.resume_after_gate_1(image_id)
  Returns: {status}

POST /api/tasks/{task_id}/gate1_reject/
  Body: {notes}
  Action: updates task.gate_1_notes, resets to 'queued' for ARIA revision
  Returns: {status}

POST /api/tasks/{task_id}/gate2_approve/
  Body: {packaging_output_id}
  Action: calls aria.resume_after_gate_2(packaging_output_id)
  Returns: {status}

GET /api/tasks/
  Returns: all tasks with status, paginated

Wire all endpoints in config/urls.py.
Protect with login_required for now.
```

---

### Milestone 4.2 — Celery Background Tasks

```
Create apps/pipeline/tasks.py

Celery is needed so ARIA runs in the background without blocking the web request.
Long image generation API calls cannot run synchronously.

from celery import shared_task

@shared_task
def run_aria_pipeline(task_id):
    from apps.pipeline.agents.aria import ARIAAgent
    agent = ARIAAgent(task_id)
    agent.run()

@shared_task  
def resume_aria_gate1(task_id, image_id):
    from apps.pipeline.agents.aria import ARIAAgent
    agent = ARIAAgent(task_id)
    agent.resume_after_gate_1(image_id)

Create config/celery.py and wire to settings.
Add CELERY_BROKER_URL = env('REDIS_URL') to settings.py.

Test: start Redis locally, start Celery worker:
  celery -A config worker --loglevel=info
```

---

## PHASE 5 — Admin Dashboard
**Goal:** The dashboard is live, beautiful, functional with all three panels.

---

### Milestone 5.1 — Dashboard Base Layout

```
Create the BBROSE Design OS admin dashboard.

Build a single-page HTML/CSS/JS dashboard at /dashboard/ using Django templates.
No external CSS framework. Write custom CSS.

Aesthetic: dark luxury. Deep charcoal background (#0D0D0D), rose gold accents (#B5895A),
warm cream text (#F5EDD6), matte surface panels.
Font: system serif for headings, monospace for agent logs.

Three-panel layout:

LEFT PANEL (280px) — Task Queue
  - Input field: "Give ARIA a task..." with submit button
  - List of all tasks with status badges
  - Status colors: running=amber, awaiting_gate=rose, completed=green, failed=red
  - Click task to load it in center panel

CENTER PANEL (flexible) — Active Task View
  Shows based on task status:
  
  [RUNNING]: Live agent activity feed (polls every 2 seconds)
    Shows logs in real-time: agent name + action + timestamp
  
  [AWAITING_GATE_1]: Approval gallery
    3 images side by side
    Under each: direction name, QA score, QA notes
    Approve button (selects this image) + Reject with notes
  
  [AWAITING_GATE_2]: 3D mockup review
    Pacdora render (or spec sheet if no API yet)
    Approve Final / Request Revision
  
  [COMPLETED]: Output summary
    Approved image + spec sheet + download links

RIGHT PANEL (300px) — Brand Intelligence Sidebar
  Shows live: current brand brief, active color systems, recent approvals
  This is the "brain panel" — always visible

All API calls from the frontend use fetch() to the Django endpoints from Milestone 4.1.
No React. Pure HTML/CSS/JS.
```

---

### Milestone 5.2 — Live Activity Feed

```
Make the agent activity log update in real-time.

In the center panel, when a task is in 'running' status:
- Poll GET /api/tasks/{task_id}/status/ every 2 seconds using setInterval
- Append new log entries to the feed as they arrive
- Each log entry shows: [timestamp] [agent_name] action_text
- Agent names get colored labels: ARIA=rose, CreativeDirector=purple, 
  PromptEngineer=teal, ImageProducer=amber, QAReviewer=coral
- When status changes to awaiting_gate_1, stop polling and render the gallery
- Smooth fade-in animation on each new log entry

This is the "watch ARIA work" experience.
```

---

### Milestone 5.3 — Gate 1 Approval Gallery

```
Build the Gate 1 image approval UI.

When task status = awaiting_gate_1:
  - Load all GeneratedImages for this task
  - Display as a 3-column gallery
  - Each card shows:
    * Generated image (large, full width of card)
    * Direction name
    * QA score badge (green if ≥7, amber if 5-6, red if <5)
    * QA notes collapsed, expand on click
    * "Select This Design" button
  
  Below gallery:
    * Text area: "Send back to ARIA with notes..."
    * "Request Revision" button

On "Select This Design":
  - POST to /api/tasks/{id}/gate1_approve/ with image_id
  - Show loading state
  - Center panel transitions to "Handing off to Pacdora..."

On "Request Revision":
  - POST to /api/tasks/{id}/gate1_reject/ with notes
  - ARIA restarts with the new context
```

---

## PHASE 6 — Product Catalog Integration
**Goal:** Your existing product catalog (Excel with IDs and PNGs) lives in the system.

---

### Milestone 6.1 — Product Import Command

```
Create apps/core/management/commands/import_products.py

This command imports products from a CSV file (exported from your Excel).

CSV format expected:
product_id, name, category, year, status, dimensions, finish_notes, notes

python manage.py import_products --file products_2025.csv --brand_id 1

Features:
- Skips duplicates (checks product_id)
- Reports: X created, Y skipped, Z errors
- Links to PackagingStructure if structure_id column exists in CSV
- Links to ColorSystem if color_system_id column exists

Also create a bulk PNG import:
python manage.py import_product_images --folder /path/to/png/folder --brand_id 1
  Matches PNG filenames to product_id values in database.
```

---

## PHASE 7 — Testing and Hardening
**Goal:** The full pipeline runs without breaking on real BBROSE products.

---

### Milestone 7.1 — End-to-End Pipeline Test

```
Run the full pipeline on a real product from your catalog.

Test script: apps/pipeline/tests/test_full_pipeline.py

Test sequence:
1. Load brand BBROSE from database
2. Load product BBR-CO-001 (or first product in catalog)
3. Create DesignTask: "Create a luxury packaging concept for this product"
4. Run ARIAAgent synchronously (not via Celery) for testing
5. Verify at each stage:
   - AgentLog entries created ✓
   - CreativeBrief created with directions ✓
   - GeneratedImages created (3) ✓
   - QA reviews saved ✓
   - Task status = awaiting_gate_1 ✓
6. Simulate Gate 1 approval: call resume_after_gate_1(first_image_id)
7. Verify:
   - PackagingOutput created ✓
   - Spec sheet populated ✓
   - Task status = awaiting_gate_2 ✓
8. Simulate Gate 2 approval
9. Verify task status = completed ✓

Print full log output to console.
Document any failures and fix before launch.
```

---

### Milestone 7.2 — Error Handling and Fallbacks

```
Add robust error handling throughout the pipeline.

1. If Claude API fails: retry once after 5 seconds, then fail gracefully
2. If OpenAI image API fails: log the error, mark image as failed, continue with remaining
3. If Pacdora API fails: save spec sheet, set pacdora_render_url to empty, 
   dashboard shows spec sheet with download button instead
4. If any agent produces invalid JSON: log the raw response, mark task as failed,
   send notification to admin (print to console for now)
5. Add timeout handling: all external API calls have 30 second timeouts
6. Add task retry: admin can click "Retry" on a failed task — resets status to queued
```

---

## PHASE 8 — Polish and Launch
**Goal:** The system is ready for daily use on real BBROSE products.

---

### Milestone 8.1 — Dashboard Polish

```
Final UI refinements:

1. Task creation: dropdown to optionally link to a product or campaign
2. Task history: searchable, filterable by status and date
3. Completed task view: download buttons for approved image, spec sheet PDF, dieline
4. Brand sidebar: show count of products by category, recent completions
5. Mobile responsive: dashboard works on tablet (you might approve from iPad)
6. Loading states: every API call has a loading spinner
7. Error states: clear messages when something fails with action to retry
8. Empty states: helpful message when no tasks exist yet
```

---

### Milestone 8.2 — Spec Sheet PDF Export

```
Create apps/pipeline/services/spec_sheet.py

When Gate 2 is approved, auto-generate a PDF spec sheet.

Use: reportlab or weasyprint

PDF contains:
- BBROSE header with brand name
- Product name and ID
- Approved image (thumbnail)
- Packaging structure: type, dimensions
- Material: name, finish combination
- Color codes: palette table with swatches
- Surface zones: description
- Prompt used for generation
- QA score and notes
- Approval timestamp

Save to PackagingOutput.spec_pdf field (FileField).
Downloadable from dashboard.
```

---

### Milestone 8.3 — Final Checklist Before Daily Use

```
Run through this checklist:

Environment:
  ✓ .env has all API keys filled in
  ✓ DEBUG=False in production
  ✓ PostgreSQL running and backed up
  ✓ Redis running for Celery
  ✓ Celery worker running

Data:
  ✓ BBROSE brand seeded with full brief
  ✓ All color systems seeded
  ✓ All aesthetic language seeded
  ✓ All material systems seeded
  ✓ All packaging structures seeded with correct dimensions
  ✓ Product catalog imported from Excel
  ✓ Product PNGs uploaded

Pipeline:
  ✓ Full end-to-end test passed (Milestone 7.1)
  ✓ Error handling verified (Milestone 7.2)
  ✓ Gate 1 approval flow working
  ✓ Gate 2 approval flow working
  ✓ Spec sheet PDF generating

Dashboard:
  ✓ Live activity feed updating in real-time
  ✓ Gallery displaying images correctly
  ✓ Approval buttons working
  ✓ Download links working
  ✓ Mobile view acceptable

You are ready to run BBROSE Design OS in daily operation.
```

---

## Quick Reference — File Structure After All Milestones

```
bbrose_design_os/
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
├── apps/
│   ├── core/
│   │   ├── models.py          ← Brand, Product, Campaign, ColorSystem, etc.
│   │   ├── admin.py
│   │   └── management/commands/
│   │       ├── seed_bbrose.py
│   │       └── import_products.py
│   ├── pipeline/
│   │   ├── models.py          ← DesignTask, AgentLog, CreativeBrief, etc.
│   │   ├── views.py           ← API endpoints
│   │   ├── tasks.py           ← Celery tasks
│   │   ├── agents/
│   │   │   ├── aria.py        ← Lead orchestrator
│   │   │   ├── creative_director.py
│   │   │   ├── prompt_engineer.py
│   │   │   ├── image_producer.py
│   │   │   ├── qa_reviewer.py
│   │   │   └── pacdora_agent.py
│   │   └── services/
│   │       ├── claude_service.py
│   │       ├── brand_context.py
│   │       └── spec_sheet.py
│   └── dashboard/
│       └── views.py           ← Dashboard HTML view
├── templates/
│   └── dashboard/
│       └── index.html         ← The full dashboard UI
├── static/
├── .env
└── requirements.txt
```

---

## API Keys Needed

| Key | Where to get | Used by |
|-----|-------------|---------|
| ANTHROPIC_API_KEY | console.anthropic.com | All agents |
| OPENAI_API_KEY | platform.openai.com | Image Producer |
| PACDORA_API_KEY | business@pacdora.com | Pacdora Agent |

---

*BBROSE Design OS — Built with Python · Django · Claude · PostgreSQL*
