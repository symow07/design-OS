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
