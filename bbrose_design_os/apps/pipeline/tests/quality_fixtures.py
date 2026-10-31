"""Explicit reviewed test images; permission tests must not bypass quality policy."""
import io
import json
from PIL import Image
from django.core.files.base import ContentFile
from apps.pipeline.services.concept_quality import DIMENSIONS, evaluate, image_sha256


def critique(score=8, hard_failures=None):
    return {'score': score, 'passed': score >= 8 and not hard_failures, 'observations': 'Fixture visual evidence', 'dimensions': {k: {'score': score, 'observation': 'Observed fixture requirement',
                              'location': 'front', 'repair': 'Increase contrast and hierarchy'} for k in DIMENSIONS},
            'hard_failures': list(hard_failures or [])}


def reviewed(image, score=8, hard_failures=None):
    if not image.image_file:
        data = io.BytesIO()
        Image.new('RGB', (64, 96), '#ddbb88').save(data, 'PNG')
        image.image_file.save('reviewed-fixture.png', ContentFile(data.getvalue()), save=False)
    review = evaluate(critique(score, hard_failures))
    review['image_sha256'] = image_sha256(image)
    image.qa_notes = json.dumps(review)
    image.qa_passed = review['passed']
    image.save()
    return image
