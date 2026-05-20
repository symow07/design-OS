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
