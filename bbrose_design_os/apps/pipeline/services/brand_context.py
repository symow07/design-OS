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
