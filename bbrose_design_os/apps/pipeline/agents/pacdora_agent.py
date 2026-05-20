import asyncio
import os
import time
import requests
from pathlib import Path
from django.conf import settings
from django.core.files.base import ContentFile
from apps.pipeline.models import PackagingOutput

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds between retries


class PacdoraAgent:

    def __init__(self, task, approved_image, log_fn=None):
        self.task = task
        self.image = approved_image
        self.log = log_fn or (lambda msg, data=None, level='info': None)

    def run(self):
        """
        Synchronous entry point called by ARIA.
        Runs the async Playwright workflow via asyncio.
        """
        self.log("Pacdora: building spec sheet")
        spec = self.build_spec_sheet()

        # Create output record immediately so Gate 2 has something to show
        output = PackagingOutput.objects.create(
            task=self.task,
            approved_image=self.image,
            spec_sheet=spec,
        )

        # Get Pacdora template ID from packaging structure
        template_id = None
        if self.task.product and self.task.product.packaging_structure:
            template_id = self.task.product.packaging_structure.pacdora_template_id

        if not template_id:
            self.log(
                "Pacdora: no template ID found for this structure — "
                "add pacdora_template_id to PackagingStructure in admin",
                level='warning'
            )
            self._flag_manual_required(output)
            return output

        # Download approved image to temp file for Playwright upload
        image_path, image_is_temp = self._download_approved_image()
        if not image_path:
            self._flag_manual_required(output)
            return output

        # Run Playwright with retry logic
        render_path = self._run_with_retries(template_id, image_path)

        # Clean up only the temp copy we created — never the canonical
        # GeneratedImage file on disk.
        if image_is_temp and os.path.exists(image_path):
            os.remove(image_path)

        if render_path:
            # Save render to PackagingOutput
            with open(render_path, 'rb') as f:
                output.pacdora_render_url = ''  # local file used
                output.dieline_file.save(
                    f"pacdora_render_task_{self.task.id}.png",
                    ContentFile(f.read())
                )
            output.save()
            os.remove(render_path)
            self.log("Pacdora: 3D render saved successfully")
        else:
            # All retries exhausted
            self.log(
                "Pacdora: all retries failed — flagging for manual completion",
                level='warning'
            )
            self._flag_manual_required(output)

        return output

    def _run_with_retries(self, template_id, image_path):
        """
        Attempts the Playwright automation up to MAX_RETRIES times.
        Returns the local render file path on success, None on failure.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            self.log(f"Pacdora: attempt {attempt} of {MAX_RETRIES}")
            try:
                render_path = asyncio.run(
                    self._playwright_workflow(template_id, image_path)
                )
                if render_path:
                    return render_path
            except Exception as e:
                self.log(
                    f"Pacdora: attempt {attempt} failed — {str(e)}",
                    level='warning'
                )
                if attempt < MAX_RETRIES:
                    self.log(f"Pacdora: retrying in {RETRY_DELAY}s")
                    time.sleep(RETRY_DELAY)

        return None

    async def _playwright_workflow(self, template_id, image_path):
        """
        Full Playwright browser session:
        Login → open template → upload artwork → screenshot render → return path
        """
        from playwright.async_api import async_playwright

        render_path = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,  # set False temporarily if debugging
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                accept_downloads=True
            )
            page = await context.new_page()

            try:
                # ── STEP 1: Login ─────────────────────────────────────────
                await page.goto(
                    "https://www.pacdora.com/login",
                    wait_until="networkidle",
                    timeout=30000
                )

                await page.fill(
                    'input[type="email"], input[name="email"]',
                    settings.PACDORA_EMAIL
                )
                await page.fill(
                    'input[type="password"], input[name="password"]',
                    settings.PACDORA_PASSWORD
                )
                await page.click(
                    'button[type="submit"], .login-btn, .sign-in-btn'
                )

                # Wait for dashboard to confirm login
                await page.wait_for_url(
                    "**/dashboard**",
                    timeout=20000
                )
                self.log("Pacdora: logged in successfully")

                # ── STEP 2: Open template ─────────────────────────────────
                await page.goto(
                    f"https://www.pacdora.com/editor/{template_id}",
                    wait_until="networkidle",
                    timeout=30000
                )
                self.log(f"Pacdora: template {template_id} loaded")

                # Wait for editor canvas to be ready
                await page.wait_for_selector(
                    '.editor-canvas, .design-canvas, [class*="canvas"]',
                    timeout=20000
                )

                # ── STEP 3: Upload artwork ────────────────────────────────
                # Click upload trigger if file input is hidden
                upload_trigger = page.locator(
                    '[class*="upload-button"], [class*="upload-area"], '
                    '.upload-design, [aria-label*="upload"]'
                ).first

                if await upload_trigger.count() > 0:
                    await upload_trigger.click()
                    await page.wait_for_timeout(500)

                # Set the file on the input
                file_input = page.locator('input[type="file"]').first
                await file_input.set_input_files(image_path)

                self.log("Pacdora: artwork uploaded — waiting for render")

                # Wait for the 3D preview to update with the artwork
                await page.wait_for_timeout(4000)

                # ── STEP 4: Trigger 3D render view ───────────────────────
                # Try to find and click the 3D preview button if present
                render_btn = page.locator(
                    '[class*="3d"], [class*="preview"], '
                    '.view-3d, [aria-label*="3D"]'
                ).first

                if await render_btn.count() > 0:
                    await render_btn.click()
                    await page.wait_for_timeout(3000)

                # ── STEP 5: Screenshot the render ────────────────────────
                # Find the 3D render container
                render_container = page.locator(
                    '[class*="3d-view"], [class*="render"], '
                    '[class*="preview-container"], .mockup-viewer'
                ).first

                render_path = str(
                    Path(settings.MEDIA_ROOT) /
                    f"renders/pacdora_task_{self.task.id}.png"
                )
                os.makedirs(os.path.dirname(render_path), exist_ok=True)

                if await render_container.count() > 0:
                    await render_container.screenshot(path=render_path)
                else:
                    # Fallback: screenshot the full page centered
                    await page.screenshot(
                        path=render_path,
                        clip={"x": 300, "y": 80, "width": 800, "height": 700}
                    )

                self.log("Pacdora: render screenshot captured")

            except Exception:
                # Capture page state so a failed scraper run is debuggable
                # (selectors below are best-guess and may drift with the
                # Pacdora UI — these artifacts are the only way to tell why).
                try:
                    debug_dir = Path(settings.MEDIA_ROOT) / "pacdora_debug"
                    os.makedirs(debug_dir, exist_ok=True)
                    stamp = int(time.time())
                    await page.screenshot(
                        path=str(debug_dir / f"task_{self.task.id}_{stamp}.png"),
                        full_page=True
                    )
                    html_path = debug_dir / f"task_{self.task.id}_{stamp}.html"
                    html_path.write_text(await page.content())
                    self.log(
                        f"Pacdora: debug artifacts saved to {debug_dir}",
                        level='warning'
                    )
                except Exception as dbg_err:
                    self.log(
                        f"Pacdora: failed to capture debug artifacts — {dbg_err}",
                        level='warning'
                    )
                # Re-raise so _run_with_retries can catch and retry
                raise
            finally:
                await context.close()
                await browser.close()

        return render_path

    def build_spec_sheet(self):
        """Builds the handoff spec from task and product data."""
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
        return spec

    def _download_approved_image(self):
        """
        Resolves the approved image to a local path for Playwright upload.

        Returns (path, is_temp): is_temp=True means we created the file and
        the caller must delete it; is_temp=False means it is the canonical
        GeneratedImage file and must NOT be deleted.
        """
        try:
            # If file is saved locally, use it directly (do not delete it).
            if self.image.image_file and self.image.image_file.name:
                return self.image.image_file.path, False

            # Otherwise download from URL into a temp copy we own.
            temp_path = str(
                Path(settings.MEDIA_ROOT) /
                f"temp/approved_task_{self.task.id}.png"
            )
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)

            response = requests.get(self.image.image_url, timeout=30)
            response.raise_for_status()
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            return temp_path, True

        except Exception as e:
            self.log(
                f"Pacdora: failed to download approved image — {str(e)}",
                level='error'
            )
        return None, False

    def _flag_manual_required(self, output):
        """
        Marks the output as needing manual Pacdora completion.
        Dashboard will show an upload field at Gate 2 instead of the auto render.
        """
        output.spec_sheet['manual_pacdora_required'] = True
        output.spec_sheet['manual_reason'] = (
            "Playwright automation failed after 3 retries. "
            "Upload Pacdora render manually from Gate 2 dashboard."
        )
        output.save()
        self.log(
            "Pacdora: marked for manual completion — "
            "dashboard will prompt you at Gate 2",
            level='warning'
        )
