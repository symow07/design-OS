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
