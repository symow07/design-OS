from pathlib import Path

from apps.core.models import (
    STATUS_CANONICAL,
    Brand,
    PackagingStructure,
    Product,
)


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
    for cs in brand.color_systems.filter(status=STATUS_CANONICAL):
        context += f"\n### {cs.system_id} — {cs.name}\n"
        context += f"Palette: {cs.palette}\n"
        context += f"Image generation context: {cs.image_generation_context}\n"

    context += "\n## Aesthetic Language\n"
    for al in brand.aesthetic_language.filter(status=STATUS_CANONICAL):
        context += f"\n### {al.aesthetic_id} — {al.name}\n"
        context += f"{al.core_description}\n"
        context += f"Product prompt seed: {al.prompt_seed_product}\n"

    context += "\n## Material Language\n"
    for ml in brand.material_systems.filter(status='approved'):
        context += f"\n### {ml.material_id} — {ml.name}\n"
        context += f"Prompt descriptors: {ml.prompt_descriptors}\n"

    return context


def get_brand_hexes(brand_id):
    """Return the canonical brand hex colours (e.g. ['#E8B4B8', ...]).

    Pulled from every canonical ColorSystem's ``palette`` JSON (a list of
    ``{role, name, hex, pantone, usage}`` swatches). Used by the deterministic
    QA palette-distance check. Swatches without a hex are skipped.
    """
    brand = Brand.objects.get(id=brand_id)
    hexes = []
    for cs in brand.color_systems.filter(status=STATUS_CANONICAL):
        for swatch in (cs.palette or []):
            hex_val = (swatch or {}).get('hex') if isinstance(swatch, dict) else None
            if hex_val:
                hexes.append(hex_val)
    return hexes


def build_product_context(task, profile=None):
    """The design SUBJECT: the selected product record + campaign.

    (2026-07-04) The Creative Director previously received only the task text
    and brand mood — the product picked in the UI never reached the model, so
    directions were generic brand wallpaper. This block makes the design
    about THIS product. (2026-07-07) With no record, the identified product
    profile (resolve_product_profile) fills in so directions still target the
    right product and carton form.
    """
    parts = []
    p = getattr(task, "product", None)
    if p is not None:
        parts.append(f"Name: {p.name} ({p.product_id})")
        parts.append(f"Category: {p.get_category_display()}")
        if p.product_type:
            parts.append(f"Type: {p.product_type}")
        if p.dimensions:
            parts.append(f"Physical format: {p.dimensions}")
        if p.finish_notes:
            parts.append(f"Finish notes: {p.finish_notes}")
        if p.notes:
            parts.append(f"Product notes: {p.notes}")
        if p.color_system:
            parts.append(
                f"Assigned color system: {p.color_system.system_id} — {p.color_system.name}"
            )
    elif profile:
        from apps.pipeline.services.product_profile import profile_text
        parts.append(profile_text(profile))
    c = getattr(task, "campaign", None)
    if c is not None:
        parts.append(f"Campaign: {c.name} — {c.direction}")
        if c.aesthetic_notes:
            parts.append(f"Campaign aesthetic notes: {c.aesthetic_notes}")
    return "\n".join(parts) if parts else (
        "No product record selected — derive the subject from the task text."
    )


def get_design_references(limit=None, task=None, profile=None):
    """Paths of the reference designs the Creative Director should study.

    With a ``task``, selection is PRODUCT-AWARE (2026-07-06): the indexed
    library (DesignReference rows, vision-tagged at import) is scored
    against the task's product + text and the best matches win — with 90+
    files, "newest N" stopped being meaningful. Without a task, or when the
    index is empty, falls back to the newest files on disk.
    """
    from django.conf import settings

    limit = limit if limit is not None else settings.MAX_DESIGN_REFERENCES
    if task is not None:
        from apps.pipeline.services.reference_index import select_references
        try:
            selected = select_references(task, limit, profile=profile)
            if selected:
                return selected
        except Exception:  # noqa: BLE001 — never block generation on the index
            pass
    ref_dir = Path(settings.MEDIA_ROOT) / "references"
    if not ref_dir.is_dir():
        return []
    files = [
        p for p in ref_dir.iterdir()
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p) for p in files[:limit]]


_STOPWORDS = frozenset(
    "a an the and or for of me my make design box new generate create want "
    "with using i to in on".split()
)


def find_similar_products(brand_id, category, task_text, limit=5):
    """Products actually relevant to the task, ranked by keyword overlap.

    (2026-07-04) The old version ignored ``task_text`` entirely and returned
    the first five active products labeled "similar" — actively misleading
    the Creative Director. Now: score by token overlap between the task text
    and each product's name/type/notes; only matched products are returned.
    """
    products = Product.objects.filter(brand_id=brand_id, status='active')
    if category:
        products = products.filter(category=category)

    tokens = {
        w for w in ''.join(
            ch if ch.isalnum() else ' ' for ch in (task_text or '').lower()
        ).split()
        if len(w) > 2 and w not in _STOPWORDS
    }
    scored = []
    for p in products.values(
        'product_id', 'name', 'category', 'year', 'product_type',
        'finish_notes', 'notes',
    ):
        haystack = ' '.join(str(v) for v in p.values()).lower()
        score = sum(1 for t in tokens if t in haystack)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda sp: -sp[0])
    return [p for _, p in scored[:limit]]


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
