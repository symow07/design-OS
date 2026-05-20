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
                    n=1,
                    timeout=60,  # image gen can be slow
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
                img_response = requests.get(image_url, timeout=30)
                if img_response.status_code == 200:
                    img.image_file.save(
                        f"task_{self.task.id}_var_{i+1}.png",
                        ContentFile(img_response.content)
                    )

                generated.append(img)
                self.log(f"Image Producer: saved variation {i+1}")

            except Exception as e:
                self.log(f"Image Producer: failed on variation {i+1} — {str(e)}", level='error')
                # Continue to next image instead of aborting the batch
                continue

        return generated
