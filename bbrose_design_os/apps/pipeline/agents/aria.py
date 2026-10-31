from apps.pipeline.services.cost_ledger import BudgetExceededError as _RescueBudgetError
import functools
import traceback

from apps.pipeline.models import DesignTask, AgentLog, CreativeBrief
from apps.pipeline.agents.creative_director import CreativeDirectorAgent
from apps.pipeline.agents.prompt_engineer import PromptEngineerAgent
from apps.pipeline.agents.image_producer import ImageProducerAgent
from apps.pipeline.agents.qa_reviewer import QAReviewerAgent
from django.conf import settings

# Auto-revision caps — keep a full run within a sane $/latency budget.
# MAX_REVISION_PASSES lives in settings (env-tunable, default 1, 2026-07-06).
MAX_IMAGES_PER_PASS = 3       # at most 3 images regenerated per revision pass
REVISION_SCORE_THRESHOLD = 7  # top QA score below this (or zero passes) → revise

#: THE CLEAN-UP OF 2026-10-04 (E8, on the owner's approved list): the pre-2A run path — a brief holding directions
#: but no planned design intent, run straight to Gate 1 — is removed, with the "rerun prompts" and "rerun creative"
#: doors. A design started that way is refused BY NAME wherever it would run again: the doors that would queue it
#: (apps/pipeline/views.py `_pre_2a_refusal`) and `ARIAAgent.run`, which fails it before anything is asked or spent.
PRE_2A_BRIEF_RETIRED = "PRE_2A_BRIEF_RETIRED"
PRE_2A_BRIEF_RETIRED_WORDS = ("This design was started before directions were planned, and that old way of running it "
                              "has been removed — it can't be run again. Start a new design from its brief; nothing "
                              "was spent.")


def pre_2a_brief(task) -> bool:
    """True for a design whose brief holds directions but no planned design intent — the removed pre-2A shape."""
    brief = CreativeBrief.objects.filter(task=task).first()
    return bool(brief and brief.directions and not brief.design_intent)


def crash_safe(fn):
    """Any unhandled exception in a pipeline stage marks the task 'failed'
    (with error_message + traceback in AgentLog) instead of stranding it in an
    intermediate status forever (Milestone 8.2 / audit C2). Applied to run()
    and every resume_* entry point."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        from apps.pipeline.services.authored_master import is_authored
        if is_authored(self.task):
            # Stale legacy messages cannot generate, reinterpret or approve an authored master.
            self.log("Authored master: use its authoring page; legacy pipeline action refused.")
            return None
        # Bind this task as the cost-ledger context so every Claude/image call
        # made during the stage is attributed to it (Milestone 12.2). A
        # BudgetExceededError raised mid-stage is caught here and fails the
        # task with the cap message, like any other error.
        # [His goal of 2026-10-13, (1): "NO check ever stops a design."] and the drawing's own bounds kept for the whole
        # stage (``keeps_bounds``): a value past one is brought to it, and said beside Approve — 125 stopped on one
        from apps.pipeline.services.cost_ledger import task_cost_context
        try:
            with task_cost_context(self.task):
                return keeps_bounds(fn)(self, *args, **kwargs)
        except Exception as e:  # noqa: BLE001 — terminal safety net
            self._fail(str(e), tb=traceback.format_exc())
    return wrapper


def concepts_to_draw(task, prompts: list, expected_variations):
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (11): "a test mode that draws ONE concept instead of
    three".] The concepts a design draws of those planned: one where it is the executor's test run
    (``DesignTask.options["one_concept"]``), every one otherwise — ``(prompts, the variations it expects)``."""
    if (getattr(task, "options", None) or {}).get("one_concept") and len(prompts) > 1:
        return prompts[:1], (expected_variations[:1] if expected_variations else expected_variations)
    return prompts, expected_variations


def keeps_bounds(fn):
    """[His goal of 2026-10-13, (1).] A stage that keeps the drawing's own bounds (``graph.bounds_kept``) — a value past
    one is brought to it, and each said beside Approve once the stage has run (``ARIAAgent._say_bounds_kept``). Every
    ``crash_safe`` stage keeps them, and the two that end their own failures (a concept redrawn, the concepts drawn again
    with references)."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        from apps.ire.graph import bounds_kept
        with bounds_kept() as brought:
            result = fn(self, *args, **kwargs)
        if brought:
            self._say_bounds_kept(brought)
        return result
    return wrapper


#: §BH57(a)4 — the house library described to the planner. Titles, what each shows, why it was retrieved. NEVER a
#: path: the design_context leak discipline forbids a file locator reaching a text agent. Never a permission
#: either, because nothing here is approved — the words say so to the model as well as to a reader.
#: [his test findings on design 121, 2026-10-07, item 4] each library entry named by its kind, never by its file
_LIBRARY_KIND_WORDS = {"HISTORICAL_DESIGN_REFERENCE": "a past BBROSE design",
                       "MATERIAL_LIBRARY": "a picture from the materials library"}


def candidate_reference_context(candidates, names=()) -> str:
    """The house library, in words, for the planner. [His test findings on design 121, 2026-10-07, item 4: "Earlier
    designs may inform style only, never names."] each entry by its kind and its style — never its file's name, nor the
    names and copy its description quotes (``other_designs.style_only``): 'Juicy Lips', 'OMG Lip Honey', BBROSE Colorete
    reached 121's planner so."""
    if not candidates:
        return ""
    from apps.pipeline.services.other_designs import style_only
    lines = []
    for c in candidates[:10]:
        what = style_only((getattr(c, "description", "") or "").strip().replace("\n", " "), names)
        why = (getattr(c, "relevance_reason", "") or "").strip()
        kind = getattr(c, "source_type", "") or "?"
        lines.append("- %s%s%s" % (
            _LIBRARY_KIND_WORDS.get(kind, "a library entry"),
            (" — " + what[:160]) if what else "",
            (" (retrieved because: %s)" % why[:110]) if why else ""))
    return ("THE HOUSE LIBRARY HOLDS THESE, retrieved for this brief. They are DESIGN KNOWLEDGE — what BBROSE and "
            "its material library already contain. Let them inform palette, motif language, finish and "
            "composition. They are NOT approved visual references, none of their artwork is attached, and you "
            "must not describe copying any of them.\n" + "\n".join(lines))


#: [§BH71 PART 2: §BH57(a)5's `web_reference_context`, which described web sources a person had approved to the planner,
#: is retired with the session that fed it — no source was ever approved in time for a design; the trend board's
#: words reach the planner now (apps/pipeline/services/trend_board.py words_block)]


def candidate_sources(candidates) -> dict:
    """{source_type: count} — for the log line, so a reader sees WHICH library answered."""
    out = {}
    for c in candidates:
        k = getattr(c, "source_type", "") or "?"
        out[k] = out.get(k, 0) + 1
    return out


def spending_context(method):
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        from apps.pipeline.services.cost_ledger import task_cost_context
        with task_cost_context(self.task):
            return method(self, *args, **kwargs)
    return wrapped


class ARIAAgent:

    def __init__(self, task_id):
        self.task = DesignTask.objects.get(id=task_id)
        self.brand_id = self.task.brand.id

    def log(self, action, payload=None, agent='ARIA', level='info'):
        AgentLog.objects.create(
            task=self.task,
            agent_name=agent,
            action=action,
            payload=payload,
            level=level
        )

    def _reference_manifest(self):
        """B4b-3B: the deterministic uploaded-reference manifest for THIS
        task, built once per agent run from persisted rows and audit-logged
        (metadata only — never bytes, paths or URLs). Product Container only:
        other targets get an empty dict so no container reference semantics
        can leak into their prompts (§19/§20)."""
        cached = getattr(self, "_ref_manifest", None)
        if cached is not None:
            return cached
        from apps.pipeline.services.reference_manifest import (
            build_task_reference_manifest)
        if self.task.design_target != 'product_container':
            # §BH69(2): any kind of design may carry inspiration pictures — its manifest holds THEM alone (their words
            # reach the planner; no container reference semantics, and no file, ever does)
            if not self.task.references.filter(kind='inspiration_picture').exists():
                self._ref_manifest = {}
                return self._ref_manifest
            manifest = build_task_reference_manifest(self.task)
            manifest = dict(manifest, entries=[e for e in manifest["entries"]
                                               if e["category"] == 'inspiration_picture'])
            manifest["reference_count"] = len(manifest["entries"])
            self._ref_manifest = manifest
            return self._ref_manifest
        manifest = build_task_reference_manifest(self.task)
        # §17 audit: the manifest the pipeline will use, recorded through the
        # existing AgentLog mechanism (schema, ordered entries, availability,
        # eligibility, usage policy — no file bytes).
        self.log("ARIA: reference manifest built "
                 f"({manifest['reference_count']} uploaded reference(s))",
                 payload=manifest)
        self._ref_manifest = manifest
        return self._ref_manifest

    def _missing_keys(self):
        """Human-readable list of unset API credentials, or '' if all present.

        The generation pipeline genuinely needs these — Creative Director and QA
        call Claude, the Image Producer calls OpenAI — so we fail fast with an
        actionable message up front instead of letting the provider SDK raise a
        cryptic 'Could not resolve authentication method' error mid-run.
        """
        missing = []
        if not settings.ANTHROPIC_API_KEY:
            missing.append("ANTHROPIC_API_KEY (design directions + QA)")
        if not settings.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY (image generation)")
        return ", ".join(missing)

    @crash_safe
    def run(self):
        # the clean-up of 2026-10-04 (E8): a design started on the removed pre-2A path fails by name first — before
        # the key check, so its reason is never "add a key and retry" for a retry that is refused
        if pre_2a_brief(self.task):
            self._fail(f"{PRE_2A_BRIEF_RETIRED}: {PRE_2A_BRIEF_RETIRED_WORDS}")
            return
        missing = self._missing_keys()
        if missing:
            self._fail(
                f"Missing API key(s): {missing}. Add them to your .env, then "
                f"click Retry to run the AI pipeline."
            )
            return

        # Phase 2A-4 routing. Three durable states decide what a (re-)run means:
        #   1. planned + selected  → render variations of the chosen direction
        #   2. planned, unselected → stay paused (a restart must not re-plan)
        #   3. nothing yet         → plan directions and pause for selection
        #   [a legacy brief — directions, no design intent — took the pre-2A pipeline until the clean-up of
        #   2026-10-04 removed it; such a brief is refused by name at the top of run()]
        brief = CreativeBrief.objects.filter(task=self.task).first()
        if brief and brief.design_intent and brief.selected_direction_id:
            return self._generate_from_selected_direction(
                feedback=self.task.gate_1_notes or None)
        if brief and brief.design_intent:
            # [his final goal, 2026-10-05, B4: "NO PROMPT STEP ... He picks a picture."] planned, no picture chosen: one
            # picture for each direction — again, with his notes, when he asked for changes at Gate 1; never re-planned
            return self._render_each_direction(feedback=self.task.gate_1_notes or None)
        if not (brief and brief.directions):
            # §BH71 PART 2: current trends for its product type, before its directions — the board built (or finished
            # after a restart) and shown ticked while the review window is open; its words reach the planner once he
            # presses on or the window closes. A batch run uses every picture without waiting; a board with nothing
            # to choose from, or one that failed, waits for nothing.
            from apps.pipeline.services import trend_board
            # [his goal of 2026-10-06, item 1] the form it is made in, and whose word that is, said once at its start
            from apps.pipeline.targets.container import FORM_SAID, form_said
            said = form_said(self.task)
            if said and not self.task.logs.filter(action__startswith=FORM_SAID).exists():
                self.log(said)
            if trend_board.review(self) == trend_board.WAITING:
                return
            return self._run_direction_planning()

        # unreachable since the pre-2A path left (the refusal at the top takes every brief that would reach
        # here) — and if it is ever reached, it fails closed by name rather than leaving the design queued
        self._fail(f"{PRE_2A_BRIEF_RETIRED}: {PRE_2A_BRIEF_RETIRED_WORDS}")

    # --- Phase 2A-4: direction planning and selected-direction rendering ------

    @crash_safe
    def _run_direction_planning(self):
        """Plan only: DIP context → structured Creative Director → persist the
        design_intent/1.1 document → pause. No PromptEngineer, no image call, no
        Gate-1 concepts. The pause is durable — it lives in task status + brief
        rows, and a restarted worker lands back here without re-planning."""
        self.task.status = 'running'
        self.task.save()
        self.log("ARIA: planning design directions (no rendering yet)")

        profile = self._product_profile()
        directive = self._target().concept_prompt_profile(self)
        # 2A-6D: a replan carries corrective feedback in gate_1_notes (the
        # same revision channel the legacy Gate-1 reject path uses); planning
        # threads it to the Creative Director as revision feedback.
        planning_feedback = (self.task.gate_1_notes or '').strip() or None
        if planning_feedback:
            self.log("ARIA: applying replan feedback to direction planning")
        cd_agent = CreativeDirectorAgent(
            self.task, self.brand_id,
            log_fn=self._log_for('CreativeDirector'),
            feedback=planning_feedback,
            product_profile=profile,
            target_directive=directive,
        )
        # §BH69(2): an inspiration picture not yet read (its read on the start page failed, or the page ran no script)
        # is read now, against this design, BEFORE a direction is written — its words reach the planner below
        from apps.pipeline.services import inspiration
        if self.task.references.filter(kind=inspiration.KIND).exists():
            inspiration.readings_for(self.task, read_missing=True)
        # B4b-3B §12: the owner's uploaded references reach direction
        # planning as categorised REFERENCE-ONLY guidance (empty task → None
        # → planning unchanged)
        from apps.pipeline.services.reference_manifest import (
            creative_director_reference_context)
        cd_agent.uploaded_reference_context = \
            creative_director_reference_context(self._reference_manifest())

        # §BH57(a)4 — THE PIPELINE ASKS FOR REFERENCES. One caller, and it was a page; §BH56 measured task 84
        # with zero candidates. The run asks the library itself now, before a single direction is written.
        # It reads them; it does not approve them (concept_references: "never automatic").
        try:
            from apps.pipeline.services.concept_references import build_candidates
            # `profile` is the local resolved above and already handed to the Creative Director. The first
            # version of this line read `self.product_profile`, which is not an attribute of this class —
            # AttributeError, caught below, and reported as the library being unavailable. Task 85 ran his
            # brief with SIXTEEN candidates waiting and the log saying there were none.
            candidates = build_candidates(self.task, profile=profile or None)
            from apps.pipeline.services.other_designs import names_of_other_designs
            cd_agent.candidate_reference_context = candidate_reference_context(
                candidates, names=names_of_other_designs(self.task))
            self.log("ARIA: house library consulted "
                     f"({len(candidates)} candidate reference(s) read, none approved)",
                     payload={"count": len(candidates),
                              "by_source": candidate_sources(candidates),
                              "approved": 0,
                              "note": "candidates are the planner's knowledge; visual use still "
                                      "requires a person (concept_references)"})
        except Exception as exc:  # noqa: BLE001 — the library is context, never fatal to a design
            # THE TYPE IS ALWAYS NAMED. This sentence used to read "house library unavailable", which is a
            # claim about the house's data that this code cannot make: the exception it caught was a wrong
            # attribute name of mine. Wire 5's handler names the type and would have said `AttributeError`
            # in the first line of the log; this one did not, and that is what hid the defect for a whole
            # run of his own brief.
            if isinstance(exc, _RescueBudgetError):
                raise
            self.log("ARIA: house library not consulted (%s) — continuing without candidates"
                     % type(exc).__name__, level='warning')

        # §BH71 PART 2 — THE TREND BOARD'S WORDS reach the planner: the pictures he kept ticked, read into words,
        # never a picture, its title or its link. [It replaces §BH57(a)5's session, which searched four fixed queries
        # and gave the planner only what a person had approved — nothing, every design, because approval came after]
        from apps.pipeline.services import trend_board
        # [his goal for the pitch, 2026-10-15, A (1): "RESEARCH FIRST ... Write a short TREND BRIEF"] written from the
        # board before the directions, and the first thing its words carry
        trend_board.write_brief(self.task, log=self.log)
        trends = trend_board.words_block(self.task)
        if trends:
            cd_agent.web_reference_context = trends
        board = trend_board.board_of(self.task)
        if board is None:
            self.log("ARIA: no trend board for this design — the directions are made without trends")
        else:
            how = board.confirmed_how
            if not how:
                how = board.status.lower()
            self.log("ARIA: %d trend picture(s) reached the planner in words (%s)" % (len(board.used_at_confirm), how),
                     payload=trend_board.summary(board))

        # Read-only DIP context, fail-soft: the actor is the workflow user; a
        # missing or unauthorized actor means design proceeds without context.
        context = None
        try:
            from apps.pipeline.design_context import (
                build_design_context, to_generator_entries,
            )
            context = build_design_context(
                self.task.created_by, cd_agent._brief())
            cd_agent.dip_context = to_generator_entries(context)
            self.log("ARIA: design-intelligence context "
                     f"({context['metadata']['included']} reference(s), "
                     f"{context['metadata']['authorization']})",
                     payload={k: context['metadata'][k] for k in
                              ('authorization', 'channel_result_counts',
                               'included', 'context_hash')})
        except Exception as rescue_error:  # noqa: BLE001 — context is optional, never fatal
            if isinstance(rescue_error, _RescueBudgetError):
                raise
            self.log("ARIA: design-intelligence context unavailable — continuing "
                     "without references", level='warning')

        result = cd_agent.run_structured()
        if result is None or not result.ok:
            codes = "; ".join(result.codes) if result else "no result"
            self._fail(f"Direction planning failed validation: {codes}")
            return
        document = result.document
        from apps.pipeline.direction_signature import SHOWN_ALIKE_KEY, shown_alike
        alike = shown_alike(result)
        self.log("ARIA: structured directions validated", payload={
            "generator_schema": result.generator_schema,
            "output_schema": result.output_schema,
            "prompt_template_version": result.prompt_template_version,
            "provider_model": result.provider_model,
            "attempts": result.attempts,
            "warnings": list(result.warnings),
            # [his test blocker on design 123, 2026-10-09, (2)] the "not distinct" checks the three still fail after
            # their one retry, and which attempts came back so — read for the note beside them; None where they passed
            SHOWN_ALIKE_KEY: alike,
        })
        if alike:
            # [his goal of 2026-10-10, item 1] any check, said as it is
            self.log("ARIA: the three directions still failed a check after one retry — they go on to be drawn anyway, "
                     "with a note, and you choose", level='warning')

        CreativeBrief.objects.update_or_create(
            task=self.task,
            defaults={
                "directions": document["directions"],
                "design_intent": {key: value for key, value in document.items()
                                  if key != "directions"},
                "retrieved_references": (context or {}).get("references", []),
                "selected_direction_id": "",
                "direction_selected_at": None,
            },
        )
        # [his final goal, 2026-10-05, B4: "NO PROMPT STEP. Three directions planned privately and validated. Three
        # truly different concepts drawn straight away."] no pause for a direction: each is drawn now, and the
        # picture he picks at Gate 1 names the direction the design goes on in
        # Replan feedback is consumed by the successful plan (H10 semantics:
        # notes clear once acted on; history lives in the archive log).
        if planning_feedback:
            self.task.gate_1_notes = ''
        self.task.save()
        self.log("ARIA: three design directions planned and validated — drawing one picture for each")
        self._render_each_direction()

    def _load_selected_direction(self):
        """Reassemble and re-validate the persisted document, then resolve the
        selected direction by its STABLE id. Fails closed — never falls back to
        another direction."""
        from apps.pipeline.design_intent import (
            DesignIntentError, validate_design_intent_document,
        )
        brief = CreativeBrief.objects.filter(task=self.task).first()
        if not (brief and brief.design_intent and brief.selected_direction_id):
            raise ValueError("no persisted direction selection to resume from")
        document = {**brief.design_intent, "directions": brief.directions}
        try:
            validate_design_intent_document(document)
        except DesignIntentError as exc:
            raise ValueError(
                f"persisted design intent failed validation ({exc.code}): {exc}"
            ) from exc
        matches = [direction for direction in document["directions"]
                   if direction.get("direction_id") == brief.selected_direction_id]
        if len(matches) != 1:
            raise ValueError(
                f"selected direction {brief.selected_direction_id!r} does not "
                "resolve to exactly one persisted direction")
        return document, matches[0]

    @crash_safe
    def _generate_from_selected_direction(self, feedback=None):
        """Render exactly three variations WITHIN the selected direction, then
        Gate 1. Creative Director and DIP context are never called here; a
        retry or restart reuses the same persisted direction input."""
        # 2C-2C-CORR-1 §9 defence in depth: worker scheduling can never
        # bypass the generation-prerequisites gate — a composite task whose
        # Gate-1 configuration is incomplete HOLDS here with zero provider
        # calls. Non-composite tasks are always ready (legacy unchanged).
        from apps.pipeline.services import gate1_checkpoint as ckpt
        ready, missing = ckpt.generation_prerequisites(self.task)
        if not ready:
            ckpt.record_prerequisites(self.task, ready, missing)
            self.task.status = ckpt.HOLD_STATUS
            self.task.save()
            self.log("ARIA: Gate-1 generation HELD — configuration "
                     "incomplete (" + ", ".join(missing) + "); no provider "
                     "call was made",
                     payload={"missing_prerequisites": missing},
                     level='error')
            return
        document, direction = self._load_selected_direction()

        self.task.status = 'running'
        self.task.save()
        self.log(f"ARIA: rendering three variations of your selected direction "
                 f"'{direction['name']}' ({direction['direction_id']})",
                 payload={"selected_direction_id": direction["direction_id"],
                          "design_intent_schema": document["schema_version"]})
        if feedback:
            self.log("ARIA: applying your Gate 1 feedback to this revision")

        if ((self.task.options or {}).get('rescue_repair_pending') or
                ((self.task.options or {}).get('concept_quality') and self.task.images.filter(superseded=False).exists())):
            self._repair_concepts(force=bool(feedback), rounds=1 if feedback else 2)
            self._finish_concept_review([])
            return
        images, qa_results = self._render_variations(direction, feedback=feedback)
        if images is None:
            return                                    # _render_variations failed the task

        self._repair_concepts()
        self._check_concepts(images)
        self.task.status = 'awaiting_gate_1'
        self.task.save()
        self._finish_concept_review(images)

    @crash_safe
    def _render_each_direction(self, feedback=None):
        """[His final goal, 2026-10-05, B4: "Three truly different concepts drawn straight away. Each picture shows a
        name and one sentence; the details folded. He picks a picture."] One picture for each planned direction, each
        bound to its direction by id; no direction is chosen for him first. The plan is re-validated, never re-made;
        the generation prerequisites hold here as they do for a chosen direction."""
        from apps.pipeline.design_intent import DesignIntentError, validate_design_intent_document
        from apps.pipeline.services import gate1_checkpoint as ckpt
        ready, missing = ckpt.generation_prerequisites(self.task)
        if not ready:
            ckpt.record_prerequisites(self.task, ready, missing)
            self.task.status = ckpt.HOLD_STATUS
            self.task.save()
            self.log("ARIA: Gate-1 generation HELD — configuration incomplete (" + ", ".join(missing)
                     + "); no provider call was made", payload={"missing_prerequisites": missing}, level='error')
            return
        brief = CreativeBrief.objects.filter(task=self.task).first()
        document = {**brief.design_intent, "directions": brief.directions}
        try:
            validate_design_intent_document(document)
        except DesignIntentError as exc:
            self._fail(f"persisted design intent failed validation ({exc.code}): {exc} — no images were generated")
            return
        directions = document["directions"]
        self.task.status = 'running'
        self.task.save()
        self.log("ARIA: drawing one picture for each direction — "
                 + "; ".join("'%s' (%s)" % (d["name"], d["direction_id"]) for d in directions),
                 payload={"direction_ids": [d["direction_id"] for d in directions],
                          "design_intent_schema": document["schema_version"]})
        if feedback:
            self.log("ARIA: applying your Gate 1 feedback to this revision")
        if ((self.task.options or {}).get('rescue_repair_pending') or
                ((self.task.options or {}).get('concept_quality') and self.task.images.filter(superseded=False).exists())):
            self._repair_concepts(force=bool(feedback), rounds=1 if feedback else 2)
            self._finish_concept_review([])
            return
        images, qa_results = self._render_variations(None, feedback=feedback, directions=directions)
        if images is None:
            return
        self._repair_concepts()
        self._check_concepts(images)
        self.task.status = 'awaiting_gate_1'
        self.task.save()
        self._finish_concept_review(images)

    @crash_safe
    def redraw_concept(self, image_id):
        from apps.pipeline.targets.container.readable import backdrop_for, REDRAW_PROMPT
        parent = self.task.images.get(pk=image_id, superseded=False)
        with parent.image_file.open('rb') as source:
            backdrop = backdrop_for(source.read())
        self._repair_concepts(force=True, rounds=1, only_id=image_id,
                              instruction=REDRAW_PROMPT.format(backdrop=backdrop['words']), edit_parent=True)
        self._check_concepts(self.task.images.filter(superseded=False,
                             reference_provenance__repair_parent_image_id=image_id))
        self._finish_concept_review([])

    def _check_concepts(self, images):
        """[His test blocker on design 122, 2026-10-07, item 2: "Never show me a concept the system can't draw. Check each
        picture's readability BEFORE showing it".] Where its target reads a concept's map (a container), every concept
        is checked — and redrawn where its background is the blocker — before the design is shown at Gate 1."""
        check = getattr(self._target(), "check_concepts", None)
        if check is None or not images:
            return
        try:
            check(self, list(images))
        except Exception as exc:  # noqa: BLE001 — the check never ends a design whose concepts are drawn and paid for
            if isinstance(exc, _RescueBudgetError):
                raise
            self.log("ARIA: the concepts could not all be checked just now — they are shown, and the one you choose is "
                     "checked again before it is drawn", level="warning",
                     payload={"error": "%s: %s" % (type(exc).__name__, str(exc)[:300])})

    def _render_variations(self, direction, feedback=None, directions=None):
        """Exactly three variation prompts → three images → QA. Returns
        (images, qa_results); (None, None) after _fail.

        2B-3V §4/§5/§6: a target may impose a structured variation contract
        (named identities + seven-axis diversity + per-variation reference
        subsets), validated BEFORE any image call. When the target returns a
        plan, the generic PromptEngineer variation path is bypassed; a failed
        contract fails the render with ZERO image calls. Targets without a
        plan (packaging) keep the generic path byte-for-byte."""
        profile = self._product_profile()

        expected_variations, expected_plan_hash, diversity_ok = None, "", None
        require_visual = False
        variation_contract = {}
        # [his final goal, 2026-10-05, B4] the three directions, one picture each — or three variations of the one
        # direction a picture already chose
        plan = (self._target().gate1_direction_plan(self, directions) if directions
                else self._target().gate1_variation_plan(self, direction))
        if plan is not None:
            # every raw response preserved for audit, pass or fail (§5) —
            # matches the regeneration path's audit discipline.
            # [his test findings on design 121, item 2] a refused check says so in its line: the feed read every one
            # as "the prompts checked — three different concepts", 121's refusal too
            from apps.pipeline.direction_signature import SHOWN_ALIKE_KEY, shown_alike
            alike = shown_alike(plan)
            self.log("Gate-1 variation contract result" + ("" if plan.ok else " — refused")
                     + (" — too alike twice, drawn anyway" if alike else ""),
                     payload={"ok": plan.ok, "attempts": plan.attempts,
                              "codes": list(plan.codes),
                              # [his test blocker on design 123, (2)] the concept step's own, read for the note
                              SHOWN_ALIKE_KEY: alike,
                              "provider_model": plan.provider_model,
                              "raw_responses": [r[:20000]
                                                for r in plan.raw_responses]},
                     agent='PromptEngineer',
                     level='info' if plan.ok else 'error')
            if not plan.ok:
                self._fail(
                    "Gate-1 variation contract not satisfied after the bounded "
                    "repair (" + "; ".join(plan.codes) + ") — zero images were "
                    "generated")
                return None, None
            prompts = plan.prompts
            plan_obj = getattr(self.task, "concept_influence_plan", None)
            expected_plan_hash = getattr(plan_obj, "plan_hash", "") or ""
            expected_variations = [p.get("variation_id") for p in prompts]
            diversity_ok = True          # the structured gate passed
            # CORR-2: per-variation routing enforces grounding when references
            # are assigned; the union require_visual flag stays off so a
            # no-reference container still renders the structured (ungrounded)
            # contract instead of being blocked.
            require_visual = False
            # §4/§6: keep each variation's structured record (signatures,
            # native-reconstruction plan, ASSIGNED reference subset) so it can
            # be persisted per image below — not discarded after validation.
            variation_contract = {
                v.get("variation_id"): v
                for v in (plan.payload or {}).get("variations", [])}
        else:
            directive = self._target().concept_prompt_profile(self)
            pe_agent = PromptEngineerAgent(
                directions or [direction], self._target().concept_structure_id(self),
                log_fn=self._log_for('PromptEngineer'),
                feedback=feedback,
                product_profile=profile,
                reference_anatomy=self._top_reference_anatomy(profile),
                target_directive=directive,
                variation_mode=not directions,
            )
            # B4b-3B §13 (generic path; the container structured contract
            # carries the same context through its product block)
            from apps.pipeline.services.reference_manifest import (
                prompt_engineer_reference_context)
            pe_agent.uploaded_reference_context = \
                prompt_engineer_reference_context(self._reference_manifest())
            # §BH71 PART 2: the trend board's words, beside his own references', under their own heading
            from apps.pipeline.services import trend_board
            pe_agent.trend_context = trend_board.words_block(self.task)
            # [his test blocker on design 123, 2026-10-09, (1)] a carton continuing its approved container keeps its look
            from apps.pipeline.targets.composite import continuation_words
            pe_agent.continuation = continuation_words(self.task) or None
            prompts = pe_agent.run()
            if directions:
                # [his final goal, B4] one prompt for each direction, bound by its id — never three of one
                from apps.pipeline.services.gate1_prompts import (PROMPTS_NOT_BOUND_TO_DIRECTIONS, PROMPTS_REPAIR,
                                                                  bound_to_directions)
                bound = bound_to_directions(prompts, directions)
                if bound is None:
                    # [B4c] asked once more, with why, before anything stops — the plan is already paid for
                    self.log("ARIA: the prompts were not one for each direction (%s) — asking once more"
                             % [p.get("direction_id") or p.get("direction_name") for p in prompts], level='warning')
                    pe_agent.feedback = "\n".join(x for x in (feedback, PROMPTS_REPAIR) if x)
                    prompts = pe_agent.run()
                    bound = bound_to_directions(prompts, directions)
                if bound is None and len(prompts) == len(directions):
                    # [his goal of 2026-10-10, item 1: "NO planner check ever stops a design"] one prompt for each
                    # direction, not named for them after the one more ask: bound by their order, and the note says so
                    from apps.pipeline.direction_signature import SHOWN_ALIKE_KEY
                    named = [p.get("direction_id") for p in prompts]
                    bound = [dict(p, direction_id=d["direction_id"], direction_name=d["name"])
                             for p, d in zip(prompts, directions)]
                    self.log("Gate-1 prompts: bound by order", level='warning', payload={SHOWN_ALIKE_KEY: {
                        "codes": ["%s: the prompts named %s" % (PROMPTS_NOT_BOUND_TO_DIRECTIONS, named)],
                        "alike_attempts": [1, 2], "attempts": 2}})
                if bound is None:
                    self._fail(f"{PROMPTS_NOT_BOUND_TO_DIRECTIONS}: the prompts name the directions "
                               f"{[p.get('direction_id') for p in prompts]}, not one for each of "
                               f"{[d['direction_id'] for d in directions]} — no images were generated")
                    return None, None
                if not all(p.get("direction_id") for p in prompts):
                    self.log("ARIA: the prompts named their directions but not their ids — each bound by its "
                             "direction's name")
                prompts = bound
            elif len(prompts) != 3:
                self._fail(
                    f"Prompt Engineer produced {len(prompts)} variation "
                    "prompts; exactly 3 are required — no images were generated")
                return None, None

        # [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (11): "a test mode that draws ONE concept instead of
        # three"] the executor's test runs only (``DesignTask.options["one_concept"]``) — never his designs' default:
        # the three directions planned and checked as ever, one concept drawn
        drawn, expected_variations = concepts_to_draw(self.task, prompts, expected_variations)
        if len(drawn) < len(prompts):
            self.log("ARIA: test run — one concept drawn of the %d planned" % len(prompts))
        prompts = drawn
        ip_agent = ImageProducerAgent(
            self.task, prompts, log_fn=self._log_for('ImageProducer'),
            product_profile=profile,
            require_visual=require_visual,
            expected_plan_hash=expected_plan_hash,
            expected_variations=expected_variations,
            diversity_ok=diversity_ok,
        )
        images = ip_agent.run()
        if not images:
            self._fail(getattr(ip_agent,'input_hold_reason',None) or "Image Producer generated no images")
            return None, None
        self._supersede_replaced(images)
        self._persist_variation_contract(images, variation_contract)

        qa_agent = QAReviewerAgent(
            images, self.brand_id, log_fn=self._log_for('QAReviewer'),
            product_profile=profile,
        )
        return images, qa_agent.run()

    #: fields of container_gate1_variations/1.0 persisted per image (§4/§6).
    _VARIATION_CONTRACT_FIELDS = (
        "title", "typography_signature", "composition_signature",
        "motif_signature", "cap_body_signature", "decoration_zone_signature",
        "color_field_signature", "finish_signature",
        "native_reconstruction_plan", "reference_ids")

    def _persist_variation_contract(self, images, contract):
        """§4: write each variation's structured signatures + native-
        reconstruction plan onto its image's reference_provenance. The
        assigned/opened/passed reference sets are written authoritatively by
        the ImageProducer from the ACTUAL per-variation routing (CORR-2 §5),
        so this method never touches them — it only adds the signatures."""
        if not contract:
            return
        for img in images:
            prov = dict(img.reference_provenance or {})
            entry = contract.get(prov.get("variation_identity"))
            if not entry:
                continue
            prov["container_variation_contract"] = {
                k: entry.get(k) for k in self._VARIATION_CONTRACT_FIELDS
                if k != "reference_ids"}
            img.reference_provenance = prov
            img.save(update_fields=["reference_provenance"])

    # --- candidate generation + revision helpers ---------------------------

    def _structure_id(self):
        if self.task.product and self.task.product.packaging_structure:
            return self.task.product.packaging_structure.structure_id
        return None

    def _log_for(self, agent_name):
        """Build a log_fn bound to a sub-agent's name."""
        return lambda msg, data=None, level='info': self.log(
            msg, data, agent=agent_name, level=level
        )

    def _product_profile(self):
        """Resolve (and memoize per ARIA instance) the task's product identity."""
        if not hasattr(self, '_profile_cache'):
            from apps.pipeline.services.product_profile import resolve_product_profile
            self._profile_cache = resolve_product_profile(self.task, log=self.log)
        return self._profile_cache

    def _top_reference_anatomy(self, profile):
        """Deep anatomy of the single closest reference (2026-07-07), or None.
        Gives the Prompt Engineer concrete house vocabulary for scale,
        placement and finishes. Never blocks generation."""
        try:
            from apps.pipeline.services.reference_index import (
                select_reference_records,
            )
            rows = select_reference_records(self.task, 1, profile=profile)
            return (rows[0].anatomy or None) if rows else None
        except Exception as rescue_error:  # noqa: BLE001
            if isinstance(rescue_error, _RescueBudgetError):
                raise
            return None

    def _supersede_replaced(self, new_images):
        """Mark every OTHER image on the task superseded once a new generation
        pass lands (Milestone 11.3). History is kept — never deleted — and the
        API returns the current set by default. No-op when the new pass
        produced nothing, so the prior set stays current."""
        if not new_images:
            return
        from apps.pipeline.models import GeneratedImage
        new_ids = [img.id for img in new_images]
        replaced = (GeneratedImage.objects
                    .filter(task=self.task, superseded=False)
                    .exclude(id__in=new_ids)
                    .update(superseded=True))
        if replaced:
            self.log(f"ARIA: superseded {replaced} image(s) from earlier passes")

    def _repair_concepts(self, force=False, rounds=2, only_id=None, instruction='', edit_parent=False, manual_rerun=False):
        """Append immutable children; resume budget-paused attempts without repurchase."""
        import uuid
        from django.db import transaction
        from apps.pipeline.services.concept_quality import image_verdict, repair_rounds_used
        from apps.pipeline.models import GeneratedImage
        for _ in range(rounds):
            with transaction.atomic():
                locked = DesignTask.objects.select_for_update().get(pk=self.task.pk)
                options = dict(locked.options or {})
                if options.get('rescue_reference_review_required'):
                    self.log('Reference refresh needs reconciliation; its saved replies must be reviewed before another paid revision.')
                    return
                if options.get('rescue_repair_inflight'):
                    self.log('A repair is active or needs reconciliation before another paid attempt.')
                    return
                pending = options.get('rescue_repair_pending')
                if pending:
                    attempt, prompts = pending['attempt'], pending['prompts']
                    requested = pending['requested']
                else:
                    candidates = [img for img in self.task.images.filter(superseded=False).order_by('variation_number', 'pk')
                                  if (only_id is None or img.pk == only_id) and
                                  (force or image_verdict(img)['review_status'] == 'rejected')]
                    if not candidates:
                        return
                    used = repair_rounds_used(locked)
                    if used >= min(2, settings.MAX_REVISION_PASSES):
                        self.log('Designer review needed — the two-round repair allowance is used.')
                        return
                    attempt, prompts, requested = uuid.uuid4().hex, [], force
                    for img in candidates:
                        prov = img.reference_provenance or {}
                        prompt = {'direction_name': img.direction_name, 'direction_id': img.direction_id,
                                  'full_prompt': img.prompt_used if force else img.prompt_used + '\nTargeted art-director repair:\n' + self._qa_feedback([image_verdict(img)]),
                                  'variation_id': prov.get('variation_identity', f'variation_{img.variation_number}'),
                                  'variation_number': img.variation_number,
                                  'repair_attempt_id': attempt, 'repair_parent_image_id': img.pk,
                                  'repair_root_image_id': prov.get('repair_root_image_id', img.pk)}
                        if (self.task.gate_1_notes or '').strip():
                            prompt['full_prompt'] += '\nRequested changes from the owner:\n' + self.task.gate_1_notes.strip()
                        if instruction:
                            prompt['full_prompt'] = instruction + '\nOriginal design brief (the requested backdrop above overrides its ground):\n' + prompt['full_prompt']
                        if edit_parent:
                            from apps.pipeline.services.concept_quality import image_sha256
                            prompt['repair_edit_parent_sha256'] = image_sha256(img)
                        from apps.pipeline.services.selected_concept import load_selected_variation
                        source_contract = load_selected_variation(self.task, img)
                        if source_contract and source_contract.get('verified'):
                            import hashlib
                            prompt['repair_variation_contract'] = dict(source_contract,
                                prompt=prompt['full_prompt'],
                                parent_prompt_sha256=hashlib.sha256(img.prompt_used.encode()).hexdigest(),
                                revision_instruction=instruction or self._qa_feedback([image_verdict(img)]))
                        if prov.get('container_variation_contract'):
                            prompt['container_variation_contract'] = prov['container_variation_contract']
                        if 'assigned_reference_ids' in prov:
                            prompt['assigned_reference_ids'] = prov['assigned_reference_ids']
                        prompts.append(prompt)
                    options['rescue_repair_rounds'] = used + 1
                    if manual_rerun:
                        locked.image_rerun_count += 1
                    options['rescue_repair_pending'] = {'attempt': attempt, 'prompts': prompts, 'requested': requested}
                options['rescue_repair_inflight'] = attempt
                locked.options = options
                locked.save(update_fields=['options', 'image_rerun_count'])
                self.task.options = options
                self.task.image_rerun_count = locked.image_rerun_count
            self.log(f"ARIA: revision pass {options['rescue_repair_rounds']} — repairing {len(prompts)} candidate(s)")
            try:
                images = ImageProducerAgent(self.task, prompts, log_fn=self._log_for('ImageProducer'),
                                            product_profile=self._product_profile()).run()
                for child in images:
                    parent_id = (child.reference_provenance or {}).get('repair_parent_image_id')
                    if child.image_file and parent_id:
                        GeneratedImage.objects.filter(pk=parent_id, task=self.task).update(superseded=True)
                unreviewed = [img for img in images if img.image_file and image_verdict(img)['review_status'] == 'review_pending']
                if unreviewed:
                    QAReviewerAgent(unreviewed, self.brand_id, log_fn=self._log_for('QAReviewer'),
                                    product_profile=self._product_profile()).run()
            except _RescueBudgetError:
                # A known pre-call refusal is resumable. Already paid children are
                # found by attempt+parent on the next run; their pixels are reused.
                self._release_repair(attempt, keep_pending=True)
                raise
            if len(images) != len(prompts) or any(not img.image_file or image_verdict(img)['review_status'] == 'review_pending' for img in images):
                self._release_repair(attempt, keep_pending=True)
                self.log('Review pending — recover the paid image or finish its critique before buying another revision.')
                return
            self._release_repair(attempt)
            if requested or not images:
                return

    def _release_repair(self, attempt, *, keep_pending=False):
        from django.db import transaction
        with transaction.atomic():
            locked = DesignTask.objects.select_for_update().get(pk=self.task.pk)
            options = dict(locked.options or {})
            if options.get('rescue_repair_inflight') == attempt:
                options.pop('rescue_repair_inflight', None)
                if not keep_pending and (options.get('rescue_repair_pending') or {}).get('attempt') == attempt:
                    options.pop('rescue_repair_pending', None)
                locked.options = options
                locked.save(update_fields=['options'])
            self.task.options = options

    def _needs_revision(self, qa_results):
        """Every reviewed failure needs repair; unavailable critique never buys new images."""
        return bool(qa_results) and all(r.get('review_status') in ('accepted', 'rejected') for r in qa_results) and any(r.get('review_status') == 'rejected' for r in qa_results)

    def _finish_concept_review(self, images):
        from apps.pipeline.services.concept_quality import summary
        # Readability can redraw/re-review an image. Use the persisted verdict.
        images = self.task.images.filter(superseded=False)
        quality = summary(images)
        self.task.options = dict(self.task.options or {}, concept_quality=quality)
        self.task.status = 'awaiting_gate_1'
        self.task.save(update_fields=['status', 'options'])
        self.log(quality['message'])

    def _qa_feedback(self, qa_results):
        """Concatenate QA issues into a feedback block for the next pass."""
        lines = []
        for r in qa_results:
            issues = r.get('issues') or []
            if issues:
                name = r.get('direction_name') or f"image {r.get('image_id')}"
                lines.append(f"- {name}: " + "; ".join(str(i) for i in issues))
        if not lines:
            # [his answer 4 of 2026-10-02: the mood follows the brief] the brief's own mood where it states one
            mood = str((self._product_profile() or {}).get("mood") or "").strip()
            return ("The previous renders did not meet the brand bar. Push palette "
                    "fidelity, " + ("the brief's own mood (" + mood + ")" if mood else "soft-luxury editorial mood")
                    + ", and make the packaging surface the clear hero.")
        return "QA flagged these issues with the previous renders:\n" + "\n".join(lines)

    # --- manual per-stage reruns (Milestone 11.3) ---------------------------

    @crash_safe
    def rerun_images(self):
        # Explicit redraw requests may revise accepted work; automatic repair may not.
        self._repair_concepts(force=True, rounds=1, manual_rerun=True)
        self._finish_concept_review([])

    @keeps_bounds
    @spending_context
    def regenerate_gate1_with_references(self, job_id=None):
        """Reference-grounded Gate-1 regeneration (2A-6E §6–§8): rebuild the
        three variations of the SAME selected direction, grounded in the
        user-approved concept references and their influence plan. The
        Creative Director is never rerun and the direction selection never
        changes.

        Failure semantics (2A-6E-CORR-5 §6): a regeneration failure is
        JOB-scoped — the parent task keeps its reviewable awaiting_gate_1
        state (its direction, historical concepts, approvals and influence
        plan are all still valid). Deliberately NOT @crash_safe: crash_safe
        fails the TASK, which is exactly the propagation this forbids. Any
        failure or crash marks the Gate1RegenerationJob failed with code
        GATE1_REGENERATION_FAILED and restores the task to awaiting_gate_1.
        """
        from apps.pipeline.services.authored_master import is_authored
        if is_authored(self.task):
            self.log("Authored master: legacy reference regeneration refused.")
            return
        from apps.pipeline.models import Gate1RegenerationJob

        job = (Gate1RegenerationJob.objects.filter(pk=job_id).first()
               if job_id else None)
        if job is not None and job.status != Gate1RegenerationJob.STATUS_QUEUED:
            self.log(f"ARIA: regeneration job {job.pk} is {job.status} — "
                     "duplicate delivery ignored", level='warning')
            return
        try:
            self._regenerate_gate1_impl(job)
        except Exception as exc:  # noqa: BLE001 — job-scoped, never the task
            import traceback
            self._gate1_job_failed(
                job, f"unexpected error: {exc}",
                payload={"traceback": traceback.format_exc()[-4000:]})

    def _gate1_job_failed(self, job, reason, payload=None):
        """§6: fail ONLY the regeneration job; restore the task to its
        reviewable gate state. Never the global pipeline-failed state."""
        from django.utils import timezone
        from apps.pipeline.models import Gate1RegenerationJob

        if job is not None:
            job.status = Gate1RegenerationJob.STATUS_FAILED
            job.error = reason
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "error", "finished_at"])
        self.task.refresh_from_db()
        if self.task.status != 'awaiting_gate_1':
            self.task.status = 'awaiting_gate_1'
            self.task.error_message = ''
            self.task.save(update_fields=['status', 'error_message'])
        self.log("ARIA: GATE1_REGENERATION_FAILED — " + reason
                 + " (the task remains at Gate 1; historical concepts and "
                   "approvals are untouched)",
                 payload={"code": "GATE1_REGENERATION_FAILED",
                          "job_id": job.pk if job else None,
                          **(payload or {})},
                 level='error')

    def _regenerate_gate1_impl(self, job):
        import uuid
        from django.db import transaction
        from apps.pipeline.models import Gate1RegenerationJob
        from apps.pipeline.services.gate1_regeneration import ensure_reference_refresh_enabled
        from apps.pipeline.services.concept_quality import repair_rounds_used
        ensure_reference_refresh_enabled()
        token = uuid.uuid4().hex
        with transaction.atomic():
            locked = DesignTask.objects.select_for_update().get(pk=self.task.pk)
            options = dict(locked.options or {})
            if options.get('rescue_repair_pending'):
                self._gate1_job_failed(job, 'Finish the pending concept repair before applying new references.')
                return
            if options.get('rescue_reference_review_required'):
                self._gate1_job_failed(job, 'The previous reference refresh stopped at its budget. Review its saved replies before another paid refresh.')
                return
            if options.get('rescue_repair_inflight'):
                self.log('A repair is already in progress; duplicate delivery ignored.')
                return
            if job is not None:
                job.refresh_from_db()
                if job.status != Gate1RegenerationJob.STATUS_QUEUED:
                    return
            used = repair_rounds_used(locked)
            if used >= min(2, settings.MAX_REVISION_PASSES):
                self._gate1_job_failed(job, 'Designer review needed — the two-round repair allowance is used.')
                return
            options['rescue_repair_rounds'] = used + 1
            options['rescue_repair_inflight'] = token
            locked.options = options
            locked.save(update_fields=['options'])
            self.task.options = options
            if job is not None:
                job.status = Gate1RegenerationJob.STATUS_RUNNING
                job.save(update_fields=['status'])
        self.regeneration_owned = True
        try:
            self._regenerate_gate1_body(job)
        except _RescueBudgetError:
            self._release_repair(token)
            self.task.options = dict(self.task.options or {}, rescue_reference_review_required={
                'job_id': job.pk if job else None,
                'reason': 'Budget-paused reference refresh; retained replies require reconciliation before repurchase.'})
            self.task.save(update_fields=['options'])
            raise
        with transaction.atomic():
            locked = DesignTask.objects.select_for_update().get(pk=self.task.pk)
            options = dict(locked.options or {})
            if options.get('rescue_repair_inflight') == token:
                options.pop('rescue_repair_inflight', None)
                locked.options = options
                locked.save(update_fields=['options'])
            self.task.options = options

    def _regenerate_gate1_body(self, job):
        from apps.pipeline.models import Gate1RegenerationJob
        from apps.pipeline.services.concept_references import (
            approved_references, reference_file_path)
        from apps.pipeline.services.gate1_regeneration import (
            GATE1_DIRECTIONS_RICHNESS_DIRECTIVES, GATE1_RICHNESS_DIRECTIVES, VARIATION_IDENTITIES)
        from apps.pipeline.services.gate1_prompts import (
            build_regeneration_prompts)

        if job is not None:
            job.status = Gate1RegenerationJob.STATUS_RUNNING
            job.save(update_fields=["status"])

        brief = CreativeBrief.objects.filter(task=self.task).first()
        if brief is not None and brief.design_intent and not brief.selected_direction_id:
            # [his final goal, 2026-10-05, B4] no picture picked yet: the three planned directions drawn again, one for
            # each, grounded in his references — the plan re-validated, never re-made
            from apps.pipeline.design_intent import validate_design_intent_document
            document = {**brief.design_intent, "directions": brief.directions}
            validate_design_intent_document(document)
            direction = None
        else:
            document, direction = self._load_selected_direction()
        approved = approved_references(self.task)
        plan_obj = getattr(self.task, "concept_influence_plan", None)
        if len(approved) < 2 or plan_obj is None:
            self._gate1_job_failed(
                job, "reference-grounded regeneration requires 2-4 "
                     "user-approved concept references and an influence "
                     "plan — nothing was generated")
            return
        if job is not None:
            # §10 provider-spend safety: the run must match the job's
            # recorded bindings exactly. Zero provider calls on any mismatch.
            if sorted(r.pk for r in approved) != \
                    sorted(job.approved_reference_ids):
                self._gate1_job_failed(
                    job, "approved reference set changed since the "
                         "regeneration was requested — request it again")
                return
            if plan_obj.plan_hash != job.influence_plan_hash:
                self._gate1_job_failed(
                    job, "influence plan changed since the regeneration "
                         "was requested — request it again")
                return
            if ((direction or {}).get("direction_id") or "") != job.direction_id:
                self._gate1_job_failed(
                    job, "selected direction changed since the "
                         "regeneration was requested")
                return
        missing = [row.pk for row in approved
                   if not reference_file_path(row).exists()]
        if missing:
            self._gate1_job_failed(
                job, f"approved concept reference file(s) missing on disk "
                     f"for reference id(s) {missing} — zero images were "
                     "generated")
            return

        self.task.status = 'running'
        self.task.save(update_fields=['status'])
        self.log("ARIA: reference-grounded Gate-1 regeneration of "
                 + ("the three planned directions, one picture each" if direction is None
                    else f"'{direction['name']}'")
                 + f" with {len(approved)} approved concept reference(s) (Creative Director skipped)")

        profile = self._product_profile()
        from apps.pipeline.services.product_profile import profile_text
        product_block = profile_text(profile) or (
            "Not identified — derive the product and its carton form from "
            "the creative direction; never default to a tall carton.")
        # §BH69(2) "The directions and concepts use what it read": concepts drawn again with references take the
        # design's inspiration pictures too — their words, quoted as data after the product; never a picture
        from apps.pipeline.services import inspiration
        inspired = inspiration.planner_context(self.task)
        if inspired:
            product_block = product_block + "\n\n" + inspired
        # [his answer 1 of 2026-10-02 (6badb27)] the brief's own colours, said to the step that makes the concept picture
        from apps.pipeline.services.product_profile import with_brief_colours
        product_block = with_brief_colours(product_block, profile)
        # §BH71 PART 2: and the trend board's words after them — quoted as data, never a picture
        from apps.pipeline.services import trend_board
        product_block = trend_board.with_trends(product_block, self.task)
        identities = (job.variation_identities if job is not None
                      else list(VARIATION_IDENTITIES))
        result = build_regeneration_prompts(
            direction=direction or {},
            directions=None if direction else document["directions"],   # [his final goal, B4]
            product_block=product_block,
            influence_plan=plan_obj.plan,
            plan_hash=plan_obj.plan_hash,
            reference_ids=[r.pk for r in approved],
            variation_identities=identities,
            richness_directives=GATE1_RICHNESS_DIRECTIVES if direction else GATE1_DIRECTIONS_RICHNESS_DIRECTIVES,
            log=self._log_for('PromptEngineer'),
        )
        # every raw response is preserved for audit, pass or fail (§5)
        from apps.pipeline.direction_signature import SHOWN_ALIKE_KEY, shown_alike
        self.log("Gate-1 prompts: generation result",
                 payload={"ok": result.ok, "attempts": result.attempts,
                          "codes": list(result.codes),
                          # [his test blocker on design 123, (2)] the concept step's own, read for the note
                          SHOWN_ALIKE_KEY: shown_alike(result),
                          "provider_model": result.provider_model,
                          "raw_responses": [r[:20000]
                                            for r in result.raw_responses]},
                 agent='PromptEngineer',
                 level='info' if result.ok else 'error')
        if not result.ok:
            self._gate1_job_failed(
                job, "regeneration prompts failed validation after the "
                     "bounded repair (" + "; ".join(result.codes)
                     + ") — zero images were generated",
                payload={"codes": list(result.codes)})
            return
        if job is not None and result.payload:
            # persist the validated payload: downstream reconstruction reads
            # the SELECTED variation's structured record from here
            job.prompts_payload = result.payload
            job.save(update_fields=["prompts_payload"])

        # 2B-3V §2: the canonical resolver derives the approved concept-
        # reference files from the task — the agent no longer receives an
        # independently-assembled reference list. Pre-spend re-validates the
        # approval set + influence-plan hash before any provider call.
        ip_agent = ImageProducerAgent(
            self.task, result.prompts, log_fn=self._log_for('ImageProducer'),
            product_profile=profile,
            require_visual=True,
            expected_plan_hash=plan_obj.plan_hash,
            expected_variations=identities,
        )
        images = ip_agent.run()
        if not images:
            self._gate1_job_failed(
                job, "Image Producer generated no images on the "
                     "reference-grounded regeneration")
            return
        self._supersede_replaced(images)

        qa_agent = QAReviewerAgent(
            images, self.brand_id, log_fn=self._log_for('QAReviewer'),
            product_profile=profile,
        )
        qa_agent.run()
        self._check_concepts(images)

        self.task.status = 'awaiting_gate_1'
        self.task.save(update_fields=['status'])
        if job is not None:
            from django.utils import timezone
            job.status = Gate1RegenerationJob.STATUS_COMPLETED
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "finished_at"])
        self._finish_concept_review(images)
        self.log("ARIA: reference-grounded regeneration complete — back at "
                 "Gate 1 with material provenance recorded"
                 + (f" (job {job.pk})" if job is not None else ""))

    def _target(self):
        """The Design Target strategy configuring the shared pipeline for
        this task (Phase A). Defaults to packaging."""
        from apps.pipeline.targets import get_target
        return get_target(getattr(self.task, 'design_target', None))

    @crash_safe
    def resume_after_gate_1(self, approved_image_id):
        """Called when you approve an image at Gate 1.

        The Design Target strategy decides what to produce next (packaging =
        dieline dimension estimate → dimension gate; other targets own their
        own backbone). The concept-generation half above is target-shared.
        """
        from apps.pipeline.models import GeneratedImage

        image = GeneratedImage.objects.get(id=approved_image_id, task=self.task)
        from apps.pipeline.services.gate1_review import image_is_selectable
        if not image_is_selectable(image):
            self._finish_concept_review([image])
            self.log('This concept cannot be approved: current quality review is missing or failed.', level='warning')
            return
        image.is_approved = True
        image.save()

        self.task.status = 'gate_1_approved'
        self.task.save()
        self.log(f"ARIA: Gate 1 approved — image {approved_image_id}")

        self._target().begin_output(self, image)

    def _run_dieline_estimate(self, image):
        """Dieline path: estimate dimensions, then pause for human confirmation."""
        from apps.pipeline.agents.dieline_agent import DielineAgent
        from apps.pipeline.models import PackagingOutput

        agent = DielineAgent(
            self.task,
            log_fn=lambda msg, data=None, level='info': self.log(msg, data, agent='Dieline', level=level)
        )
        result, job = agent.run()

        PackagingOutput.objects.create(
            task=self.task,
            approved_image=image,
            spec_sheet=self._build_dieline_spec(result),
            dieline_job=job,
        )

        self.task.status = 'awaiting_dimensions'
        self.task.save()
        self.log("ARIA: reached dimension gate — confirm carton dimensions to generate the dieline")

    def _build_dieline_spec(self, result):
        from apps.pipeline.agents.dieline_agent import TEMPLATE_TYPE
        product = self.task.product
        return {
            'backend': 'dieline',
            'template': TEMPLATE_TYPE,               # [his second goal of 2026-10-06, item 2] the reverse tuck end
            'scenario': result.scenario,
            'product_name': product.name if product else 'Unknown',
            'product_type': getattr(product, 'product_type', '') if product else '',
            'estimated_dimensions': result.model_dump(),
        }

    @crash_safe
    def resume_after_container_profile(self, packaging_output_id, confirmed_profile):
        """Called when the reviewer confirms the container profile at its gate.

        The container's answer to resume_after_dimensions: build the silhouette
        backbone from the confirmed profile and reconstruct the editable
        concept-sheet .ai (native vector) + PNG preview, then advance to Gate 2
        for review through the canonical Design Review Board.
        """
        from apps.pipeline.models import PackagingOutput
        from apps.pipeline.targets.container import reconstruct_container

        output = PackagingOutput.objects.get(id=packaging_output_id)
        # [the owner's finding on design 119, 2026-10-03: "NO SILENT FALLBACK"] the front its map draws, checked where it
        # is drawn — drawn whole, every part it names — else back to Gate 1, with why; never drawn from the form's own
        # layout instead
        from apps.pipeline.targets.container import front_checked
        archetype = (confirmed_profile or {}).get("archetype") or ((output.spec_sheet or {}).get(
            "container_profile") or {}).get("archetype")
        if front_checked(self, output, archetype) is None:
            return
        self.log("ARIA: container profile confirmed — reconstructing container .ai")
        try:
            reconstruct_container(self, output, confirmed_profile)
        except Exception as e:  # noqa: BLE001 — recoverable: back to the gate
            if isinstance(e, _RescueBudgetError):
                raise
            spec = output.spec_sheet or {}
            spec['generation_error'] = str(e)
            output.spec_sheet = spec
            output.save(update_fields=['spec_sheet'])
            self.task.status = 'awaiting_container_profile'
            self.task.save()
            self.log(f"Container: reconstruction failed — {e}", level='error')
            return
        self._show_checks_gone_past(output)            # [his goal of 2026-10-13, (1)]
        self._prepare_views(output)                    # [his goal of 2026-10-13, (6)]
        self.task.status = 'awaiting_gate_2'
        self.task.save()
        self.log("ARIA: reached Gate 2 — awaiting container approval")

    def _selected_direction(self) -> dict | None:
        """The direction the user chose at the 2A-4 pause, if any."""
        brief = getattr(self.task, 'brief', None)
        if brief is None:
            return None
        directions = brief.directions or []
        selected = getattr(brief, 'selected_direction_id', '') or ''
        for d in directions:
            if isinstance(d, dict) and d.get('direction_id') == selected:
                return d
        return directions[0] if directions and isinstance(directions[0], dict) else None

    def _carton_flats_refused(self, output, confirmed_dims) -> bool:
        """[his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4): "a standalone carton gets the same flat redraw before tracing"] The carton's own line-art motifs (``carton_front``'s lines given no container art) each redrawn
        flat once, at the front his confirmed size gives them; True, the design back at the size step and said, where
        one could not be made."""
        from apps.pipeline.targets.container import _concept_bytes, ensure_flat_motifs
        target = self._target()
        if getattr(target, "reads_carton_map", False) is not True:
            return False
        own = target.carton_front(self.task, output.spec_sheet or {}, _concept_bytes(output.approved_image), [])
        parts = [line["part"] for line in ((own or {}).get("shapes") or {}).get("lines") or []
                 if "continued" not in line]
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (2): "a motif that can't be traced cleanly ... is redrawn
        # flat and traced again"] and each solid motif its photo's trace breaks (``flat_motif.shape_whole``)
        parts += [shape["part"] for shape in ((own or {}).get("shapes") or {}).get("shapes") or []
                  if shape.get("whole") is not None and not shape["whole"]["ok"]]
        if not parts:
            return False
        from apps.pipeline.targets.packaging import seen_face_mm
        face = seen_face_mm(confirmed_dims)        # [his goal of 2026-10-13, (2)] the front as it is seen
        refused = ensure_flat_motifs(self, output, output.spec_sheet or {}, face, parts=parts)
        self._went_past(output, refused, "the carton's line art could not be redrawn flat — it is not drawn, never "
                                         "traced from its photo")
        return False

    def _went_past(self, output, codes: list, words: str) -> None:
        """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design."] Each check the
        drawing does not pass — a motif not redrawn flat, or not whole — kept on the output and said beside Approve in
        its words, with what he can do; the design goes on without the part, never traced from the photo."""
        if not codes:
            return
        from apps.dashboard.words import check_words
        from apps.ire import self_check as _sc
        spec = dict(output.spec_sheet or {})
        for code in codes:
            head, _, detail = str(code).partition(":")
            _sc.keep_shown(spec, head.strip(), (check_words(head.strip()) or words)
                           + ((" — " + detail.strip()) if detail.strip() else ""),
                           ("ask for changes to have it drawn again", "approve it as it stands"))
        output.spec_sheet = spec
        output.save(update_fields=['spec_sheet'])
        self.log("ARIA: %s — the design goes on, and each is said beside Approve" % words, level='warning',
                 payload={"codes": codes})

    def _prepare_views(self, output) -> None:
        """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (6): "SEE THE DESIGN ON THE PAGE".] The drawing's views
        made with it, here, in the pipeline's own thread (``drawing_views.prepare``) — the page then only reads files.
        Where they cannot be made now the page makes them when it asks, said in the log; never a stop."""
        from apps.pipeline import drawing_views
        try:
            drawing_views.prepare(self.task, output)
        except Exception as exc:  # noqa: BLE001 — the views are the page's to show, never the design's to stop on
            if isinstance(exc, _RescueBudgetError):
                raise
            self.log("ARIA: the drawing's views were not made now — the page makes them when it shows them",
                     level="warning", payload={"error": "%s: %s" % (type(exc).__name__, str(exc)[:300])})

    def _show_checks_gone_past(self, output) -> None:
        """[His goal of 2026-10-13, (1).] The design at Gate 2 with every check it went on past listed beside Approve, in
        its words, with the drawing's own check (``self_check.with_shown``)."""
        from apps.ire import self_check as _sc
        output.refresh_from_db(fields=["spec_sheet"])
        spec = dict(output.spec_sheet or {})
        if not spec.get(_sc.CHECKS_SHOWN_KEY):
            return
        spec[_sc.SCHEMA] = _sc.with_shown(spec.get(_sc.SCHEMA), spec)
        output.spec_sheet = spec
        output.save(update_fields=["spec_sheet"])

    @crash_safe
    def resume_after_dimensions(self, packaging_output_id, confirmed_dims,
                                panel_info_override=None):
        """Called when you confirm dimensions at the dimension gate.

        Runs the deterministic geometry engine + exporters, saves the dieline
        files onto the PackagingOutput, then advances to Gate 2.
        """
        from apps.pipeline.agents.dieline_agent import DielineAgent
        from apps.pipeline.models import PackagingOutput
        from django.core.files.base import ContentFile

        output = PackagingOutput.objects.get(id=packaging_output_id)
        job = output.dieline_job
        if job is None:
            self._fail("No dieline job linked to this output")
            return

        self.task.status = 'generating_dieline'
        self.task.save()
        self.log("ARIA: dimensions confirmed — generating dieline")

        # [the owner's finding on design 119, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7): "NO
        # SILENT FALLBACK ... Never hand me a different design"] the carton's front from its concept's map, checked
        # before anything is spent here — drawn whole, every part it names — else back to Gate 1, with why
        from apps.pipeline.targets.container import front_checked
        if front_checked(self, output, None) is None:
            return
        # [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4):
        # "a standalone carton gets the same flat redraw before tracing"] each line-art motif the carton draws from its
        # own concept — every one of a carton standing alone, the small ones a carton continuing its container is given
        # none of the container's art for — redrawn flat once, a paid picture kept on the concept, before it is traced,
        # as a container's is (his finding on 122's drawing, A1: "Never trace motifs from the concept photo"); one that
        # cannot be made, or is not whole, stops the drawing back at the size step, said — never drawn from the photo
        if self._carton_flats_refused(output, confirmed_dims):
            return
        # [his test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (1): "After
        # I pick a concept, draw ONE more picture of the same design as a flat carton layout ... never printed, read
        # into the map like the front. Every panel is drawn from it."] made and read once, kept on the concept — where
        # it cannot be made now, said, and the panels continue the front: never a refusal
        if getattr(self._target(), "reads_carton_map", False) is True and output.approved_image is not None:
            from django.conf import settings as _settings
            if _settings.DESIGN_MAP_READ:
                from apps.pipeline.targets.carton_layout import LAYOUT_NOT_MADE, ensure_layout
                unmade = []
                ensure_layout(self, output.approved_image, confirmed_dims, said=unmade)
                # [his goal of 2026-10-13, (1) and (2)] said beside Approve, never only in the log
                self._went_past(output, ["%s: %s" % (LAYOUT_NOT_MADE, why) for why in unmade],
                                "the carton's layout picture was not made")
        map_front = self._target().carton_map_front(self.task, output)
        from apps.pipeline.targets.container import flat_motif_codes
        self._went_past(output, flat_motif_codes(map_front) if map_front else [],
                        "the carton's line art is not whole in its flat redraw — it is not drawn")
        agent = DielineAgent(
            self.task,
            log_fn=lambda msg, data=None, level='info': self.log(msg, data, agent='Dieline', level=level)
        )
        product = self.task.product
        # [his go of 2026-10-02: the map path for a carton — the carton of a Complete Product has no product record, and
        # its front printed its brief's first sixty characters] the name as a container's front takes it
        from apps.pipeline.targets.container import product_name_for
        metadata = {
            'product_name': product_name_for(self.task, product)[0],
            'product_type': getattr(product, 'product_type', '') if product else '',
            'notes': self.task.task_text,
        }
        metadata = self._target().design_metadata(self.task, metadata)   # §BH55 Phase 2: a gift set says so
        # Info-panel data (2026-07-06): Product/Brand defaults merged with
        # whatever the reviewer edited at the dimension gate.
        from apps.pipeline.services.panel_info import merge_panel_info
        panel_info = merge_panel_info(self.task, panel_info_override)
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL: ... 132's sticker only the
        # name and net weight. Every back label carries the full set"] each piece his words and the product record leave
        # empty written once for the product's type (a fidelity call, kept with the design, never paid twice) before
        # the label is translated — so it is translated with his
        from apps.pipeline.services import label_copy as _label_copy
        from apps.pipeline.targets.container import label_about as _label_about
        _label_kept = {_label_copy.SCHEMA: (output.spec_sheet or {}).get(_label_copy.SCHEMA)}
        _label_copy.fill_panel(_label_kept, panel_info, (output.spec_sheet or {}).get('panel_info') or {},
                               _label_about(self.task), log=self.log)
        # Trilingual sticker (2026-07-07): translate the English copy to
        # ES + AR once, here; the result rides in panel_info and persists in
        # the spec sheet so re-exports never re-call the model.
        from apps.pipeline.services.panel_translate import TRANSLATABLE_KEYS, translate_panel_info
        # [his final goal, 2026-10-05: "redraw 119 at $0"; C5's offers taken at no cost] the translations of words he
        # has not changed are kept — the same English, translated before, is never paid for again
        previous = (output.spec_sheet or {}).get('panel_info') or {}
        unchanged = bool(previous.get('translations')) and all(
            (previous.get(k) or '').strip() == (panel_info.get(k) or '').strip() for k in TRANSLATABLE_KEYS)
        if unchanged:
            translations = previous['translations']
            self.log("ARIA: the label's English is as before — its translations kept, nothing spent")
        else:
            translations = translate_panel_info(panel_info, task=self.task, log=self.log)
        if translations:
            panel_info["translations"] = translations
            # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] the English the translations are OF — so a label
            # whose English changes after it was translated is never printed with another English's translation
            panel_info[_label_copy.TRANSLATED_ENGLISH_KEY] = {
                k: " ".join(str(panel_info.get(k) or "").split()) for k in TRANSLATABLE_KEYS if panel_info.get(k)}
        # [his final goal, 2026-10-05, B3] the back's information as he chose it at the size step: a sticker, printed on
        # the panel, or his custom sticker — from his sticker reference, read once, and his brief's "Sticker:" words
        from apps.ire import back_info as _back_info
        from apps.pipeline.services.inside_read import task_readings as _readings
        from apps.pipeline.targets.container import brief_text as _brief
        back_mode = confirmed_dims.get('back_info') or _back_info.DEFAULT_MODE
        panel_info['back_info'] = _back_info.plan(
            back_mode, _readings(self.task, kind=_back_info.KIND) if back_mode == 'custom' else [],
            _back_info.brief_sticker_words(_brief(self.task)))
        # [his final goal, C5] his choice of the stopped label's offers: fewer languages. [His second goal of
        # 2026-10-06, item 1: "Never printed inside the box; remove "info printed inside" as an option."] a size
        # confirmed with the info printed inside (119's, his morning's item 5) is drawn with everything on the sticker
        if confirmed_dims.get('label_languages'):
            panel_info['label_languages'] = list(confirmed_dims['label_languages'])
        # [his review of 119, 2026-10-05, point 6: "where my brief gives the Arabic, use my words exactly (with the
        # shadda)"] the title's Arabic is his, never the translation's, where his brief or the product record gives it
        from apps.pipeline.targets.container import arabic_name_for
        name_ar, name_ar_origin = arabic_name_for(self.task)
        if name_ar:
            panel_info["product_name_ar"], panel_info["product_name_ar_source"] = name_ar, name_ar_origin
        # [his review, C (7)] the form the written pieces are set in, measured on the back's sticker at its floor: the
        # whole label stands — a written piece shortened, or in English only, before his label is stopped for room
        panel_info.pop(_label_copy.PANEL_FORM_KEY, None)
        panel_info.pop(_label_copy.PANEL_DROPPED_KEY, None)
        if panel_info.get(_label_copy.PANEL_WRITTEN_KEY) or panel_info.get(_label_copy.PANEL_MADE_IN_KEY):
            from apps.ire.compose import label_form as _label_form
            _form = _label_form(panel_info, (confirmed_dims['width_mm'], confirmed_dims['height_mm']),
                                float(confirmed_dims.get('safe_margin_mm') or 4.0))
            panel_info[_label_copy.PANEL_FORM_KEY] = _form["form"]
            if _form["dropped"]:
                panel_info[_label_copy.PANEL_DROPPED_KEY] = list(_form["dropped"])

        # [the owner's finding on design 119, 2026-10-03: "KILL THE RASTER PATH. The flat-artwork and "background
        # pattern" image edits ... must never place AI pixels on a carton. Every panel is vector, drawn from the
        # concept's map"] No image edit is made and no picture is placed: the front is drawn from its concept's map,
        # and every other panel, flap and the glue tab on its ground (P4's flat artwork of 2026-07-04 and its
        # "background" motif of 2026-07-07 are no longer called for any carton). [The clean-up of 2026-10-04,
        # E1-E2, approved by the owner: both are removed, with the picture and the motif this call passed as None.]
        artwork_tint = map_front["ground"] if map_front is not None and map_front.get("ground") else None
        # [his final goal, 2026-10-05 (transcribed at 32e9aaf), B1: "INSIDE AND TOP PRINTING. Never leave the inside blank
        # or white. Do NOT search my past designs for it."] the inside as he chose it at the size step: his inside
        # references, each read once into its pattern and style, and his brief's "Inside:" words — else the concept's
        # own motif — in the design's own colours
        from apps.ire import inside_print
        from apps.pipeline.services.inside_read import task_readings
        from apps.pipeline.targets.container import brief_text as _brief_text
        inside_mode = confirmed_dims.get('inside_print') or inside_print.DEFAULT_MODE
        inside = inside_print.plan(inside_mode, task_readings(self.task) if inside_mode == 'referenced' else [],
                                   inside_print.brief_inside_words(_brief_text(self.task)), map_front)
        try:
            gen = agent.generate(job, confirmed_dims, metadata,
                                 artwork_tint=artwork_tint,
                                 panel_info=panel_info,
                                 # [the owner's answer of 2026-09-27: a gift set on the corrected flap]
                                 template_version=self._target().carton_template_version(self.task),
                                 map_front=map_front, inside=inside)
        except Exception as e:
            # Recoverable: send the task back to the dimension gate so the user
            # can correct values, rather than failing the whole pipeline.
            if isinstance(e, _RescueBudgetError):
                raise
            spec = output.spec_sheet or {}
            spec['generation_error'] = str(e)
            output.spec_sheet = spec
            output.save(update_fields=['spec_sheet'])
            self.task.status = 'awaiting_dimensions'
            self.task.save()
            self.log(f"Dieline: generation failed — {e}", agent='Dieline', level='error')
            return

        output.dieline_file.save(
            f"dieline_task_{self.task.id}.svg",
            ContentFile(gen['svg_string'].encode('utf-8')),
            save=False,
        )
        if gen.get('ai_path'):
            with open(gen['ai_path'], 'rb') as f:
                output.dieline_ai_file.save(
                    f"dieline_task_{self.task.id}.ai",
                    ContentFile(f.read()),
                    save=False,
                )
        if gen.get('production_pdf_path'):
            with open(gen['production_pdf_path'], 'rb') as f:
                output.production_pdf.save(
                    f"dieline_task_{self.task.id}_production.pdf",
                    ContentFile(f.read()),
                    save=False,
                )
        # Design-on-dieline preview (IRE, 2026-07-08): a PNG snapshot of the
        # editable .ai (SVG policy: no user-facing SVG). Best-effort.
        if gen.get('design_preview_png_path'):
            with open(gen['design_preview_png_path'], 'rb') as f:
                output.design_preview.save(
                    f"design_preview_task_{self.task.id}.png",
                    ContentFile(f.read()),
                    save=False,
                )
        if gen.get('design_preview_ai_path'):
            with open(gen['design_preview_ai_path'], 'rb') as f:
                output.design_preview_ai.save(
                    f"design_preview_task_{self.task.id}.ai",
                    ContentFile(f.read()),
                    save=False,
                )
        spec = output.spec_sheet or {}
        spec.pop('generation_error', None)
        spec.pop('gate_2_revision_note', None)
        # [his correction of 2026-10-07: "Never widen the carton for text"] the size the design is made at is the size
        # he confirmed; an old size's choice of the info printed inside is dropped from the record (never printed inside)
        confirmed_dims.pop('label_inside', None)
        spec['confirmed_dimensions'] = confirmed_dims
        # [his second goal of 2026-10-06, item 2] the die folded and checked before he sees it
        if gen.get('fold_check'):
            from apps.dielines.geometry.fold_check import SCHEMA as _FOLD_SCHEMA
            spec[_FOLD_SCHEMA] = gen['fold_check']
        # Audit + regeneration: what the info panel was generated from.
        spec['panel_info'] = panel_info
        # [his review, C (7)] the written pieces kept with the design (never paid twice), each shown beside Approve as
        # "not confirmed — please check", with the placeholder origin and the QR's address where they are the system's
        if _label_kept.get(_label_copy.SCHEMA):
            spec[_label_copy.SCHEMA] = _label_kept[_label_copy.SCHEMA]
        _brand_site = getattr(self.task.brand, 'website', None) if self.task.brand_id else None
        _left_off = panel_info.get(_label_copy.PANEL_DROPPED_KEY) or []
        _label_copy.show(spec, {f: panel_info.get(f) for f in panel_info.get(_label_copy.PANEL_WRITTEN_KEY) or ()
                                if f not in _left_off},
                         made_in=_label_copy.MADE_IN_PLACEHOLDER if panel_info.get(_label_copy.PANEL_MADE_IN_KEY)
                         and "made_in" not in _left_off else None,
                         qr=panel_info.get('qr_url') if _brand_site and panel_info.get('qr_url') == _brand_site else None,
                         form=panel_info.get(_label_copy.PANEL_FORM_KEY), dropped=_left_off)
        spec['flat_width_mm'] = gen['flat_width_mm']
        spec['flat_height_mm'] = gen['flat_height_mm']
        spec['panel_count'] = gen['panel_count']
        spec['warnings'] = gen['warnings']
        spec['has_production_pdf'] = bool(gen.get('production_pdf_path'))
        # §BH55 Phase 2: the carton front's type, measured where it was composed — Gate 2 reads it (§BH50(f)(3))
        from apps.ire.compose import FRONT_TYPE_KEY
        if gen.get('front_type'):
            spec[FRONT_TYPE_KEY] = gen['front_type']
        else:
            spec.pop(FRONT_TYPE_KEY, None)
        # [his review of 119, 2026-10-05, point 2] the back's copy as laid out — what moved where, and said
        from apps.ire.compose import BACK_COPY_KEY
        if gen.get('back_copy'):
            spec[BACK_COPY_KEY] = gen['back_copy']
        else:
            spec.pop(BACK_COPY_KEY, None)
        # [his final goal, 2026-10-05, B1] what the inside prints, and its own picture beside the outside's
        from apps.ire.compose import INSIDE_KEY
        if gen.get('inside_print'):
            record = dict(gen['inside_print'])
            if gen.get('design_inside_png_path'):
                from django.core.files.storage import default_storage
                with open(gen['design_inside_png_path'], 'rb') as f:
                    record['preview'] = default_storage.save(f"dielines/design_inside_task_{self.task.id}.png",
                                                             ContentFile(f.read()))
            spec[INSIDE_KEY] = record
        else:
            spec.pop(INSIDE_KEY, None)
        # [his final goal, 2026-10-05, C6] the native, layered .ai — kept beside the design's PDF-compatible .ai
        if gen.get('native_ai'):
            record = dict(gen['native_ai'])
            if record.get('built') and record.get('path'):
                from django.core.files.storage import default_storage
                with open(record['path'], 'rb') as f:
                    record['path'] = default_storage.save(f"dielines/design_native_task_{self.task.id}.ai",
                                                          ContentFile(f.read()))
            spec['native_ai/1.0'] = record
        if gen.get('drawing_views'):
            spec['drawing_views/1.0'] = gen['drawing_views']      # [his goal of 2026-10-13, (6)]
        # [his final goal, 2026-10-05, C5] a stopped label's offers, each drawn — kept beside the design for his choice
        offers = []
        import os
        from django.core.files.storage import default_storage as _store
        for row in gen.get('label_offer_previews') or []:
            kept = {k: v for k, v in row.items() if k not in ('ai', 'png', 'png_inside')}
            for k in ('ai', 'png', 'png_inside'):
                if row.get(k):
                    with open(row[k], 'rb') as f:
                        kept[k] = _store.save("dielines/label_offer_task_%d_%s" % (self.task.id, os.path.basename(row[k])),
                                              ContentFile(f.read()))
            offers.append(kept)
        if offers:
            spec['label_offers/1.0'] = offers
        else:
            spec.pop('label_offers/1.0', None)
        # [his final goal, 2026-10-05, C7] the drawing's own check — what it fixed and what it shows him; a native .ai
        # Illustrator could not build is said there too, never silently
        if gen.get('self_check'):
            from django.conf import settings as _settings

            from apps.ire import self_check as _self_check
            check = gen['self_check']
            native = spec.get('native_ai/1.0') or {}
            if _settings.NATIVE_AI_BUILD and native and not native.get('built'):
                check = _self_check.record(check['fixed'], check['shown'] + [{
                    "kind": "native file", "fixed": False,
                    "what": "the layered Illustrator file was not built (%s); the design .ai is the file to open"
                            % native.get('reason')}])
            elif native.get('built') and native.get('missing_fonts'):
                check = _self_check.record(check['fixed'], check['shown'] + [{
                    "kind": "native file", "fixed": False,
                    "what": "the layered Illustrator file sets some lines in a substitute face: %s not available to "
                            "Illustrator (installed faces are seen after Illustrator restarts)"
                            % ", ".join(native['missing_fonts'])}])
            spec[_self_check.SCHEMA] = check
        # [his goal for the pitch, 2026-10-15, B (5): "DESIGNER'S EYE: after every drawing, render it beside its concept
        # and have a vision model list every visible difference"] the carton's drawing, its front as its file prints
        # it, looked at beside its concept; what it still sees said beside Approve (a carton is drawn again from his
        # turn: the eye's fixes are the container's)
        if gen.get('design_preview_ai_path'):
            self._carton_eye(output, spec, gen['design_preview_ai_path'])
        # [his goal of 2026-10-13, (1)] every check the carton went on past said beside Approve, with its own check's
        from apps.ire import self_check as _gone_past
        if spec.get(_gone_past.CHECKS_SHOWN_KEY):
            spec[_gone_past.SCHEMA] = _gone_past.with_shown(spec.get(_gone_past.SCHEMA), spec)
        output.spec_sheet = spec
        output.save()
        self._prepare_views(output)                    # [his goal of 2026-10-13, (6)]

        self.task.status = 'awaiting_gate_2'
        self.task.save()
        self.log("ARIA: dieline ready — awaiting Gate 2 approval")

    def _carton_eye(self, output, spec, ai_path):
        """[His goal for the pitch, B (5)] the designer's eye on a carton: its front (``views_of``'s "The front") beside
        the concept picture it was drawn from; its record on the spec; what it sees kept to be shown beside Approve."""
        from django.conf import settings as _s
        if not getattr(_s, "DESIGNERS_EYE", True) or not _s.ANTHROPIC_API_KEY:
            return
        image = output.approved_image
        if image is None or not image.image_file:
            return
        from apps.ire import self_check as _sc
        from apps.pipeline.services import designers_eye as _eye
        with image.image_file.open('rb') as fh:
            concept = fh.read()
        box = _eye.design_box(spec.get('drawing_views/1.0'))
        record = _eye.check(concept, lambda: _eye.render(ai_path, box), None, log=self.log, task=self.task)
        spec[_eye.SCHEMA] = record
        for row in _eye.shown(record):
            _sc.keep_shown(spec, "DESIGNERS_EYE_DIFFERS", row["what"], ())
        self.log("ARIA: the designer's eye on the carton — %s, $%s" % (record["state"], record["cost_usd"]))

    @crash_safe
    def resume_after_gate_2(self, packaging_output_id):
        """Called when you approve the 3D mockup at Gate 2."""
        from apps.pipeline.models import PackagingOutput

        output = PackagingOutput.objects.get(id=packaging_output_id)
        output.is_final_approved = True
        output.save()

        self.task.status = 'completed'
        self.task.save()
        self.log("ARIA: pipeline completed — all outputs saved")

        # Composite orchestration (Phase C2): if this task is a stage of a
        # project, advance it (container completion → spawn packaging;
        # packaging completion → complete project). No-op for single tasks.
        if self.task.project_id:
            from apps.pipeline.targets.composite import advance_project
            advance_project(self.task.project)
            self.log("ARIA: advanced Complete Product project")

    def _say_bounds_kept(self, brought):
        """[His goal of 2026-10-13, (1).] Each value the stage's drawing brought to its bound, said beside Approve as a
        fix of the drawing's own (the self-check's "Fixed: …"), once each, and in the design's log."""
        from apps.ire import self_check as _self_check
        from apps.ire.graph import bound_words
        lines = list(dict.fromkeys(bound_words(row) for row in brought))
        output = self.task.current_output()
        if output is not None:
            spec = dict(output.spec_sheet or {})
            check = spec.get(_self_check.SCHEMA) or _self_check.record([], [])
            fixed = list(check.get("fixed") or [])
            seen = {f.get("what") for f in fixed}
            fixed += [{"kind": "the drawing's bounds", "fixed": True, "what": line} for line in lines if line not in seen]
            spec[_self_check.SCHEMA] = _self_check.record(fixed, list(check.get("shown") or []))
            output.spec_sheet = spec
            output.save(update_fields=["spec_sheet"])
        self.log("ARIA: the drawing kept its own bounds — " + "; ".join(lines), payload={"brought": brought})

    def _fail(self, reason, tb=None):
        import logging
        logging.getLogger('aria').error(f'Task {self.task.id} failed: {reason}')
        self.task.status = 'failed'
        self.task.error_message = str(reason)
        self.task.save(update_fields=['status', 'error_message', 'updated_at'])
        # Composite orchestration (Phase C2): surface a stage failure on the
        # parent project so the UI/resume knows which stage to retry.
        if self.task.project_id:
            from apps.pipeline.targets.composite import mark_project_failed
            mark_project_failed(self.task.project, self.task.stage)
        self.log(
            f"ARIA: pipeline failed — {reason}",
            payload={'traceback': tb} if tb else None,
            level='error',
        )
