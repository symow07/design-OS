from apps.pipeline.services.spend_reservation import paid_operation
import base64
import hashlib
import os
import time

import openai
import requests
from django.conf import settings
from django.core.files.base import ContentFile

from apps.pipeline.models import GeneratedImage
from apps.pipeline.services.cost_ledger import BudgetExceededError
from apps.pipeline.services.pipeline_errors import ImageDownloadError
from apps.pipeline.services import round_calls

openai.api_key = settings.OPENAI_API_KEY


#: [his goal after the pitch page, B (11): "no stops"] a concept picture asked again when the picture service fails for
#: a passing reason (a dropped connection, a 5xx, a rate limit) — this many times in all, waiting this many seconds times
#: the attempt between: the carton of his first Complete Product brief lost its trend-led concept to one "Connection
#: error"
PICTURE_ATTEMPTS = 3
PICTURE_BACKOFF = 4


def _with_retries(call, files):
    """``call()``, asked again on a passing failure (``pipeline_errors.is_transient``, never a billing refusal), its
    files read again from their start — the last failure raised."""
    from apps.pipeline.services.pipeline_errors import is_billing_error, is_transient
    for attempt in range(1, PICTURE_ATTEMPTS + 1):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 — classified here, re-raised where it is not passing
            if attempt == PICTURE_ATTEMPTS or not is_transient(exc) or is_billing_error(exc):
                raise
            for fh in files:
                fh.seek(0)
            time.sleep(PICTURE_BACKOFF * attempt)
    return None


class ImageProducerAgent:

    def __init__(self, task, prompts, log_fn=None, product_profile=None,
                 *, bundle=None, require_visual=False, expected_plan_hash="",
                 expected_variations=None, diversity_ok=None):
        self.task = task
        self.prompts = prompts
        self.product_profile = product_profile or {}
        # 2B-3V §2/§3: the ONE canonical resolver decides which image files may
        # reach the provider — approved task-scoped concept references + task
        # uploads only, never the house index. ``bundle`` is an explicit
        # override for tests; production resolves lazily from the task.
        self._bundle = bundle
        self.require_visual = require_visual
        self.expected_plan_hash = expected_plan_hash or ""
        self.expected_variations = list(expected_variations or [])
        self.diversity_ok = diversity_ok
        self.log = log_fn or (lambda msg, data=None, level='info': None)

    def _bundle_for_task(self):
        if self._bundle is None:
            from apps.pipeline.services.visual_reference_resolver import (
                resolve_visual_references)
            self._bundle = resolve_visual_references(self.task)
        return self._bundle

    def _reference_inputs(self):
        """Visual grounding for generation via the canonical resolver (2B-3V
        §2). Only task-scoped, human-authorised files reach the provider:
        approved concept references + task uploads (+ the brand logo when at
        least one design reference is present). The product-profile house
        index NEVER contributes an image file. Returns ([paths], has_logo);
        empty when nothing is authorised so the plain generate path applies."""
        return self._bundle_for_task().provider_files()

    def _reference_provenance(self, ref_paths, has_logo):
        """What ACTUALLY reached the provider (§2/§8): approved concept IDs
        whose file was passed, and every visual file as a root-relative
        string. Built strictly from the opened path list — a reference that
        did not ship cannot appear here."""
        bundle = self._bundle_for_task()
        passed = {str(p) for p in ref_paths}
        concept_ids = [r.reference_id for r in bundle.concept_references
                       if r.path in passed]

        def _display(path):
            path = str(path)
            for root in (str(settings.MEDIA_ROOT),):
                if path.startswith(root):
                    return "media/" + os.path.relpath(path, root)
            return os.path.basename(path)

        return {
            "concept_reference_ids": concept_ids,
            "approved_reference_ids": bundle.approved_reference_ids,
            "visual_files_passed": [_display(p) for p in ref_paths],
            "official_logo_included": bool(has_logo),
            "influence_plan_hash": bundle.influence_plan_hash,
            "provider_model": settings.IMAGE_MODEL,
        }

    def _uploaded_reference_paths(self) -> dict:
        """{'logo': path|None, 'grounding': [paths]} from the task's uploads.
        Empty when the task has no references (packaging parity)."""
        result = {"logo": None, "grounding": []}
        try:
            refs = list(self.task.references.all())
        except Exception:  # noqa: BLE001
            return result
        for r in refs:
            try:
                path = r.image.path
            except (ValueError, NotImplementedError):
                continue
            if not os.path.exists(path):
                continue
            if r.kind == "logo" and result["logo"] is None:
                result["logo"] = path
            elif r.kind in ("container", "label", "inspiration", "color"):
                result["grounding"].append(path)
        result["grounding"] = result["grounding"][:4]   # cap edit inputs
        return result

    def _grounded_prompt(self, full_prompt, has_logo):
        # [the clean-up's wiring check, 2026-10-04, its finding W4] the product is named "the product" — these two
        # sentences said "the carton" to every design, a bottle's and a poster's too
        logo_note = (
            "The FIRST attached image is the official BBROSE logo lockup "
            "(wordmark with a rose inside the O). Place THAT exact artwork on "
            "the product as the brand mark — do not typeset, redraw, restyle, "
            "or re-letter the brand name yourself; only its color/foil "
            "treatment may change. " if has_logo
            else ""
        )
        concept_note = (
            "Some attached images are USER-APPROVED CONCEPT REFERENCES: draw "
            "palette balance, composition discipline, motif treatment, "
            "texture layering and finishing language from them as design "
            "PRINCIPLES — never copy their layouts, patterns or "
            "illustrations, and never reproduce one recognizably. "
            if self._bundle_for_task().concept_references else ""
        )
        form = self.product_profile.get("physical_format") or ""
        form_note = (
            f"PRODUCT FORM (non-negotiable): the product is a {form} — "
            "keep exactly this physical form. " if form else ""
        )
        # §BH57(a)3: this preamble is TRUE of design references and FALSE of a lone logo. Since a lone logo now
        # opens the edit path, saying "the attached images are real BBROSE production packaging designs" when the
        # only attachment is the wordmark would replace the old lie with a new one. It says which case it is in.
        only_logo = has_logo and not self._bundle_for_task().reference_file_paths()
        grounding = (
            "STYLE GROUNDING: the ONE attached image is the official BBROSE brand mark, and nothing else is "
            "attached — there is no reference design to match. Design from the brief below alone. "
            if only_logo else
            "STYLE GROUNDING: the attached images are real BBROSE production "
            "packaging designs. Match their studio craft — wordmark treatment, "
            "typography scale and case, motif language, finish discipline, "
            "print-quality composition. Create a COMPLETELY NEW design for the "
            "brief below; never copy an attached layout. "
        )
        return (
            f"{grounding}{logo_note}{concept_note}{form_note}"
            "\n\nBRIEF: " + full_prompt
        )

    def _variation_provenance(self, bundle, prompt_data, ref_paths, has_logo,
                              assigned, opened, passed):
        """§5: per-variation provenance keeping the complete approved set, the
        ASSIGNED subset, and the OPENED/PASSED sets as DISTINCT fields — no one
        field is reused for assigned vs passed."""
        prov = self._reference_provenance(ref_paths, has_logo)
        prov.update({
            "variation_identity": prompt_data.get("variation_id") or "",
            "approved_reference_ids": bundle.approved_reference_ids,
            "assigned_reference_ids": list(assigned),
            "opened_reference_ids": list(opened),
            "passed_reference_ids": list(passed),
        })
        return prov

    def _prepare_calls(self, use_edit):
        """Resolve every prompt's provider inputs and validate pre-spend BEFORE
        any provider call. Returns a per-prompt [(ref_paths, has_logo,
        provenance)] list, or None when any pre-spend fails (→ zero calls).

        Per-variation routing (CORR-2) applies when prompts carry
        ``assigned_reference_ids`` (the container contract): each variation's
        images.edit call receives EXACTLY its assigned approved subset. Prompts
        without an assignment (packaging / generic / regeneration) keep the
        task-level union bundle — byte-identical behaviour."""
        from apps.pipeline.services.provider_prespend import (
            persist_prespend, validate_image_prespend, validate_variation_prespend)
        if getattr(self.task,'design_target',None)=='display_stand':
            # The old generic bundle cannot distinguish exact assemblies/products
            # from style references. The measured display service validates all5
            # role-bound inputs. Do not pay for a graphics-only substitute here.
            from apps.pipeline.services.provider_prespend import PreSpendResult
            result=PreSpendResult(ok=False,codes=['EXACT_DISPLAY_REFERENCE_PACK_REQUIRED'],detail={'task_id':self.task.pk,'production_use_allowed':False,'route':'Measured display concept service required; exact product and geometry inputs unresolved in legacy route.'})
            persist_prespend(self.task,result,log_fn=self.log)
            self.input_hold_reason='This display needs an exact bottle reference and an exact assembly reference before pictures can be drawn. Use the measured display concept service.'
            return None
        bundle = self._bundle_for_task()
        per_variation = use_edit and any(
            p.get("assigned_reference_ids") is not None for p in self.prompts)

        prepared, results = [], []
        if per_variation:
            for prompt_data in self.prompts:
                assigned = list(prompt_data.get("assigned_reference_ids") or [])
                ref_paths, has_logo, opened = bundle.provider_files_for(assigned)
                passed = list(opened)            # opened == passed by construction
                res = validate_variation_prespend(
                    self.task, bundle,
                    variation_id=prompt_data.get("variation_id"),
                    assigned_ids=assigned, opened_ids=opened, passed_ids=passed,
                    expected_plan_hash=self.expected_plan_hash or None)
                persist_prespend(self.task, res, log_fn=self.log)
                results.append(res)
                prepared.append((ref_paths, has_logo, self._variation_provenance(
                    bundle, prompt_data, ref_paths, has_logo, assigned, opened,
                    passed)))
        else:
            ref_paths, has_logo = ([], False)
            if use_edit:
                ref_paths, has_logo = self._reference_inputs()
            provenance = self._reference_provenance(ref_paths, has_logo)
            res = validate_image_prespend(
                self.task, bundle, opened_files=ref_paths, has_logo=has_logo,
                expected_variations=self.expected_variations,
                expected_plan_hash=self.expected_plan_hash or None,
                diversity_ok=self.diversity_ok, require_visual=self.require_visual)
            persist_prespend(self.task, res, log_fn=self.log)
            results.append(res)
            if ref_paths and res.ok:
                self.log(
                    "Image Producer: grounding generation in "
                    f"{len(ref_paths) - (1 if has_logo else 0)} reference "
                    f"design(s){' + official logo' if has_logo else ''}"
                    + (f" ({len(provenance['concept_reference_ids'])} "
                       "user-approved concept reference(s))"
                       if provenance["concept_reference_ids"] else ""),
                    data=provenance)
            prepared = [(ref_paths, has_logo, provenance) for _ in self.prompts]

        if not all(r.ok for r in results):
            codes = sorted({c for r in results for c in r.codes})
            self.log("Image Producer: pre-spend validation FAILED — zero "
                     f"provider calls ({', '.join(codes)})", level='error')
            return None
        return prepared

    def run(self):
        generated = []
        # gpt-image models accept reference images via the edit endpoint;
        # dall-e models cannot, so they keep the text-only path.
        use_edit = settings.IMAGE_MODEL.startswith('gpt-image')
        prepared = self._prepare_calls(use_edit)     # [(ref_paths, has_logo, prov)]
        if prepared is None:
            return []                                # pre-spend failed → 0 calls

        from apps.pipeline.services import gate1_checkpoint as ckpt
        checkpointed = ckpt.has_checkpoint(self.task)

        for i, prompt_data in enumerate(self.prompts):
            ref_paths, has_logo, provenance = prepared[i]
            edit_parent = prompt_data.get('repair_edit_parent_sha256')
            if edit_parent:
                parent = self.task.images.get(pk=prompt_data['repair_parent_image_id'])
                with parent.image_file.open('rb') as source:
                    parent_bytes = source.read()
                if not parent_bytes or hashlib.sha256(parent_bytes).hexdigest() != edit_parent:
                    raise ValueError('The selected redraw source changed; review it before another payment.')
                # A same-task source explicitly chosen for an edit is distinct
                # from approved creative references; record both roles honestly.
                ref_paths = list(ref_paths) + [parent.image_file.path]
                provenance = dict(provenance, repair_edit_parent_image_id=parent.pk,
                                  repair_edit_parent_sha256=edit_parent,
                                  original_concept_input={'image_id': parent.pk, 'sha256': edit_parent,
                                      'role': 'selected generated concept', 'authorization': 'explicit readability redraw'},
                                  visual_files_passed=list(provenance.get('visual_files_passed') or []) + [os.path.basename(parent.image_file.name)])
            variation_id = (prompt_data.get('variation_id')
                            or f"variation_{i + 1}")
            if prompt_data.get('repair_attempt_id'):
                existing = self.task.images.filter(reference_provenance__repair_attempt_id=prompt_data['repair_attempt_id'], reference_provenance__repair_parent_image_id=prompt_data['repair_parent_image_id']).first()
                if existing is not None:
                    generated.append(existing)
                    continue
            elif checkpointed:
                # 2C-2C-CORR-1 §4: resume at the first missing image — an
                # already-generated variation is reused, never duplicated,
                # and never costs another provider call.
                existing = ckpt.existing_variation_image(self.task,
                                                         variation_id)
                if existing is not None:
                    generated.append(existing)
                    self.log(
                        f"Image Producer: variation {variation_id} already "
                        f"generated (image {existing.id}) — reused, no "
                        "provider call")
                    continue
                ckpt.set_variation_state(self.task, variation_id,
                                         ckpt.V_GENERATING)
            self.log(f"Image Producer: generating image {i+1} of {len(self.prompts)}")

            try:
                from datetime import datetime, timezone as _tz
                _t0 = time.monotonic()
                _start_iso = datetime.now(_tz.utc).isoformat()
                if ref_paths:
                    files = [open(p, 'rb') for p in (ref_paths[:-1] if edit_parent else ref_paths)]
                    if edit_parent:
                        from io import BytesIO
                        original = BytesIO(parent_bytes)
                        original.name = os.path.basename(parent.image_file.name)
                        files.append(original)
                    try:
                        from apps.pipeline.services.cost_ledger import before_paid_call   # [his goal of 2026-10-13, (2)]
                        before_paid_call("a concept picture")
                        response = _with_retries(lambda: paid_operation(openai.images.edit, provider='openai', task=self.task, operation='image_producer',
                            model=settings.IMAGE_MODEL,
                            image=files,
                            prompt=(prompt_data['full_prompt'] + '\nThe last attached image is the owner-selected generated concept. Preserve that design exactly; earlier attachments retain their logo/reference roles.') if edit_parent else self._grounded_prompt(
                                prompt_data['full_prompt'], has_logo,
                            ),
                            size=settings.IMAGE_SIZE,
                            quality=settings.IMAGE_QUALITY_CONCEPTS,
                            n=1,
                            timeout=180,
                        ), files)
                    finally:
                        for fh in files:
                            fh.close()
                else:
                    from apps.pipeline.services.cost_ledger import before_paid_call   # [his goal of 2026-10-13, (2)]
                    before_paid_call("a concept picture")
                    response = _with_retries(lambda: paid_operation(openai.images.generate, provider='openai', task=self.task, operation='image_producer',
                        model=settings.IMAGE_MODEL,
                        prompt=prompt_data['full_prompt'],
                        size=settings.IMAGE_SIZE,
                        quality=settings.IMAGE_QUALITY_CONCEPTS,
                        n=1,
                        timeout=120,  # image gen can be slow (gpt-image more so)
                    ), ())

                _latency_ms = int((time.monotonic() - _t0) * 1000)

                # Two provider response shapes (2026-07-04): the dall-e family
                # returns an expiring signed URL; the gpt-image family returns
                # base64 (b64_json) directly — no URL, no expiry, no download.
                data = response.data[0]
                image_url = getattr(data, 'url', None)
                if not isinstance(image_url, str):
                    image_url = ''
                b64 = getattr(data, 'b64_json', None)
                if not isinstance(b64, (str, bytes)):
                    b64 = None

                # Cost ledger (Milestone 12.2): one record per image; may raise
                # BudgetExceededError to fail the task once the cap is crossed.
                # 2B-3V §8: attach the per-call observability metadata.
                from datetime import datetime, timezone as _tz
                from apps.pipeline.services.cost_ledger import (
                    provider_operation_id, provider_request_id, record_image)
                record_image(
                    settings.IMAGE_MODEL,
                    operation=f"image:{prompt_data['direction_name']}",
                    image_count=1,
                    task=self.task,
                    metadata={
                        "provider_request_id": provider_request_id(response),
                        "provider_operation_id": provider_operation_id(response),
                        "start_ts": _start_iso,
                        "end_ts": datetime.now(_tz.utc).isoformat(),
                        "latency_ms": _latency_ms,
                        "retry_number": 0,
                        "reference_ids": provenance["concept_reference_ids"],
                        "visual_filenames": provenance["visual_files_passed"],
                        "prompt_hash": hashlib.sha256(
                            prompt_data['full_prompt'].encode()).hexdigest(),
                    },
                )

                # Save to database
                img = GeneratedImage.objects.create(
                    task=self.task,
                    direction_name=prompt_data['direction_name'],
                    # [his final goal, B4] bound to the direction it was drawn for, by id
                    direction_id=prompt_data.get('direction_id') or '',
                    prompt_used=prompt_data['full_prompt'],
                    image_url=image_url,
                    variation_number=prompt_data.get('variation_number', i + 1),
                    reference_provenance={
                        **provenance,
                        **{k: prompt_data[k] for k in ('repair_attempt_id', 'repair_parent_image_id', 'repair_root_image_id') if k in prompt_data},
                        **{k: prompt_data[k] for k in ('repair_variation_contract', 'container_variation_contract') if k in prompt_data},
                        "variation_identity": (
                            prompt_data.get('variation_id')
                            or f"variation_{i + 1}"),
                    },
                )

                if b64:
                    # gpt-image path: bytes are already in hand.
                    img.image_file.save(
                        f"task_{self.task.id}_var_{i+1}.png",
                        ContentFile(base64.b64decode(b64)),
                    )
                elif image_url:
                    # dall-e path: download the durable local copy — the
                    # remote URL expires in ~1h (Milestone 8.6 / audit H1).
                    try:
                        archive_error = getattr(response, '_rescue_download_error', None)
                        if isinstance(archive_error, str) and archive_error:
                            raise ImageDownloadError(archive_error)
                        saved = getattr(response, '_rescue_paid_images', None)
                        if isinstance(saved, list) and saved:
                            from pathlib import Path
                            content = Path(saved[0]).read_bytes()
                        else:
                            content = round_calls.download_image_bytes(image_url)
                        img.image_file.save(
                            f"task_{self.task.id}_var_{i+1}.png",
                            ContentFile(content),
                        )
                    except ImageDownloadError as e:
                        img.download_failed = True
                        img.save(update_fields=['download_failed'])
                        self.log(
                            f"Image Producer: download failed for variation {i+1} "
                            f"after {DOWNLOAD_ATTEMPTS} attempts — {e}. Marked "
                            f"retryable (redownload from the gallery).",
                            level='error',
                        )
                else:
                    img.download_failed = True
                    img.save(update_fields=['download_failed'])
                    self.log(
                        f"Image Producer: provider returned neither URL nor "
                        f"base64 for variation {i+1} — marked failed.",
                        level='error',
                    )

                generated.append(img)
                if checkpointed:
                    ckpt.set_variation_state(self.task, variation_id,
                                             ckpt.V_GENERATED)
                self.log(f"Image Producer: saved variation {i+1}")

            except BudgetExceededError:
                raise
            except Exception as e:
                # Provider billing/quota refusals hit every variation the
                # same way — abort with an actionable message instead of
                # burning the loop and failing generically (2026-07-04).
                from apps.pipeline.services.pipeline_errors import (
                    BillingLimitError,
                    is_billing_error,
                )
                if is_billing_error(e):
                    if checkpointed:
                        # §4/§5: the plan and the other variations survive a
                        # billing refusal untouched; the checkpoint records
                        # the block and demands the owner acknowledgement
                        ckpt.mark_billing_blocked(self.task, variation_id)
                    # provider-side forensics (2026-07-27): the request id
                    # and SANITIZED response headers — never auth material —
                    # so a support escalation has something to cite
                    forensics = {}
                    response = getattr(e, 'response', None)
                    if response is not None:
                        safe = ('x-request-id', 'openai-organization',
                                'openai-processing-ms', 'openai-version',
                                'x-ratelimit-limit-requests',
                                'x-ratelimit-remaining-requests', 'date',
                                'cf-ray')
                        headers = getattr(response, 'headers', {}) or {}
                        forensics = {k: str(headers.get(k))
                                     for k in safe if headers.get(k)}
                    self.log(
                        "Image Producer: provider billing limit reached — aborting",
                        {'provider_forensics': forensics} if forensics else None,
                        level='error',
                    )
                    raise BillingLimitError(
                        "OpenAI account billing limit reached — image "
                        "generation refused. Add credits or raise the "
                        "spending limit at platform.openai.com → Billing, "
                        "then Retry this task."
                    ) from e
                if prompt_data.get('repair_attempt_id'):
                    # An uncertain paid attempt must be reconciled, never silently
                    # treated as an empty successful batch and purchased again.
                    raise
                self.log(f"Image Producer: failed on variation {i+1} — {str(e)}", level='error')
                # Continue to next image instead of aborting the batch
                continue

        # §BH71 PART 2 "never near-copied": each new concept compared with the trend pictures its directions used —
        # flagged beside it when close, never removed
        from apps.pipeline.services import trend_board
        trend_board.mark_near_copies(self.task, generated)
        return generated
