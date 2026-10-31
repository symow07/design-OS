"""Design Target abstraction (Phase A, 2026-07-08).

BBROSE Design OS is becoming target-driven: one shared pipeline (Creative
Director → Prompt Engineer → GPT Image 2 → QA → Gate 1 → Design Graph → IRE
→ validators → .AI), configured per Design Target rather than forked.

A ``TargetStrategy`` owns the decisions that genuinely differ between targets
— the front-half concept-structure hook and the back-half "what to produce
after Gate 1" entry. Everything else (concept generation loop, gates, the
Design Graph contract, emitters) stays shared. Phase A ships only PACKAGING,
wrapping today's behavior exactly; new targets (Product Container next) add a
strategy without touching the pipeline.
"""
from __future__ import annotations

from django.db import models


class DesignTarget(models.TextChoices):
    PRODUCT_CONTAINER = "product_container", "Product Container"
    PACKAGING = "packaging", "Packaging"
    PALETTE = "palette", "Palette"
    COMPLETE_PRODUCT = "complete_product", "Complete Product"
    GIFT_SET = "gift_set", "Gift Set"
    DISPLAY_STAND = "display_stand", "Display Stand"
    MARKETING_MATERIAL = "marketing_material", "Marketing Material"
    EXHIBITION_BOOTH = "exhibition_booth", "Exhibition Booth"
    SOCIAL_MEDIA = "social_media", "Social Media"


class TargetStrategy:
    """Base strategy. Subclasses configure the shared pipeline; they never
    reimplement it. Methods take the live ``ARIAAgent`` so a strategy can
    delegate to its existing orchestration without inverting control."""

    #: DesignTarget value this strategy handles.
    name: str = ""
    #: §BH55 Phase 2 — "A target that cannot be built is named with what it needs, not left grey." Non-empty: the
    #: target is registered but cannot yet design, and the create door refuses it BEFORE any paid work, in these words.
    needs: str = ""

    def concept_structure_id(self, aria):
        """Front half: the packaging-structure id fed to the Prompt Engineer
        (or None when the target has no structure). Default: none."""
        return None

    def concept_prompt_profile(self, aria) -> str:
        """Front half: an optional directive steering WHAT object the concept
        depicts (a carton vs a bottle vs a booth ...). Injected into the
        Creative Director / Prompt Engineer USER message only when non-empty;
        the empty default leaves those prompts byte-identical (packaging
        parity). Never touches the shared system prompt."""
        return ""

    def begin_output(self, aria, approved_image):
        """Back half: kick off deliverable production after Gate 1 concept
        approval. Each target owns its structural backbone here (packaging =
        dieline; container = silhouette; ...)."""
        raise NotImplementedError

    def review_sections(self, task) -> list[dict]:
        """Target-specific SPECIFICATIONS rows for the Design Review Board —
        ``[{"label": ..., "value": ...}]``. Pure data; the board renderer
        decides presentation. Default: none."""
        return []

    def panel_defaults(self, task, info: dict) -> dict:
        """§BH55 Phase 2: the carton's panel copy as this target speaks it (`services/panel_info.py`) — the
        product record's own words by default; a gift set's are the set's. A person still edits every field at the
        dimension gate."""
        return info

    def design_metadata(self, task, metadata: dict) -> dict:
        """§BH55 Phase 2: the words the carton's front carries under the name (`metadata["product_type"]`) —
        the record's own type by default; a gift set says it is one."""
        return metadata

    def carton_map_front(self, task, output) -> dict | None:
        """[His go of 2026-10-02: the map path for a carton.] The carton's front as its concept's map draws it — None
        by default: only a carton's own target reads one."""
        return None

    def gate2_hold(self, task, output) -> dict | None:
        """§BH55 Phase 2: the refusal Gate 2 answers with 409 when what is MEASURED on this design holds it —
        None by default. No override."""
        return None

    def carton_template_version(self, task) -> str | None:
        """The version of the straight tuck end this target's carton is drawn at on this deployment's path — None,
        the current version, by default. [The owner's answer of 2026-09-27: a gift set's is the corrected flap.]"""
        return None

    def gate1_variation_plan(self, aria, direction):
        """Front-half Gate-1 variation contract (2B-3V §4/§5/§6).

        Return a ``RegenPromptsResult`` (validated structured variations, or a
        failed result whose codes force ZERO image calls) to impose a
        target-specific variation contract on the initial selected-direction
        render — or ``None`` to keep the shared generic variation-prompt path
        untouched. Default: ``None`` (packaging parity)."""
        return None

    def gate1_direction_plan(self, aria, directions):
        """[His final goal, 2026-10-05, B4: "Three truly different concepts drawn straight away."] A target's own
        contract for the first concepts — one for each planned direction, bound by its id — or ``None`` for the shared
        prompt path (one prompt per direction). Default: ``None``."""
        return None
