"""The system's status, in a designer's words (§BH55 Phase 3, 2026-09-20).

OWNER STANDING ORDER §BH55, PHASE 3 — "Slices 3 and 4 fold in here." Slice 4 of §BH51 is the status of the system: what
is waiting, on whom, and what cannot move and why; where the production gates stand; whether the system is healthy;
what has been spent against its caps; which way cartons are drawn; what the last gates said. None of it was on a page.

Every figure is READ from what governs it, and nothing is written: the production gate record is DERIVED with
`write=False` (its builder, like the spec-pack intake's, writes by default and must not here); spend is read on the
budget refusal's own clock (cost_ledger.day_cost_usd — the rolling 24 hours), never the calendar day; the worker and
the queue are probed only when a person asks (a ping waits up to its timeout, and reading the worker's revision
dispatches a task); the Complete Product preflight is never called from here (it dispatches a task and waits up to 15 s).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings

#: statuses where a design waits on a person — in the order a design meets them
WAITING = ("awaiting_direction_selection", "awaiting_gate1_generation_configuration", "awaiting_gate_1",
           "awaiting_dimensions", "awaiting_container_profile",
           "awaiting_design_intent_confirmation", "awaiting_gate_2")
WORKING = ("queued", "running", "awaiting_trend_review", "gate_1_approved", "generating_dieline", "gate_2_approved")
SHOWN = 12
#: the brain's freshness, measured over every source it names — cached, since the sources are read to measure it
_FRESHNESS_KEY = "dashboard:brain_freshness/1"

#: how a carton is drawn — one way. [The clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow".] The
#: switches that chose between ways left with the ways they chose: the motif over every panel and the flattened
#: Illustrator file with the raster leftovers, the Pacdora backend with its agent, the structure-confirmation step with
#: its flow.
DRAWING = ("A carton is drawn one way here: from the design map of the concept you chose, on a die the dieline "
           "generator draws.")

#: what the paid steps use, read from the settings the code reads before it spends (§BH55 Phase 3, survey row 1.4)
def paid_settings() -> list:
    from django.conf import settings as s
    return [
        {"name": "The picture model", "value": s.IMAGE_MODEL,
         "words": "draws every concept"},
        {"name": "The picture size", "value": s.IMAGE_SIZE, "words": "every concept is drawn at this size"},
        {"name": "Concepts in a set", "value": "3", "words": "three are drawn for the direction you choose"},
        {"name": "Redraws allowed", "value": str(s.MAX_REVISION_PASSES),
         "words": "how many times a set of concepts may be drawn again for one design"},
        {"name": "The label copy translated", "value": "Yes" if s.PANEL_TRANSLATE_ENABLED else "No",
         "words": "the printed information is translated for the sticker when the carton is made"},
    ]


#: AI calls the spend ledger does not count toward the caps — each read in the code on 2026-09-20
NOT_COUNTED = (
    "the embeddings that index the design-intelligence corpus (no record is written)",
    "the tagging of house references when they are imported (no design is in scope)",
    "a render package's paid visual review (it keeps its own budget)",
    "the call that rewrites a concept's prompts when its references are redrawn (no design is in scope; "
    "its pictures are counted)",
    "the captions of the materials (made outside the site, with their own spend record)",
)
TIER2_WORDS = {"GREEN": "passed", "AMBER": "passed, with a known flaky test allowed once",
               "REFUSE": "refused — nothing was committed"}


def _title(task) -> str:
    """A design's name as every screen gives it (the board's `title_of`: its product and what is designed) — its brief's
    first line said a planner's code where the planner wrote one."""
    from apps.dashboard.board import title_of
    return title_of(task)


def waiting() -> dict:
    """The designs that wait on a person, grouped by what they wait for; the ones being worked on; and the stopped ones
    with their own words. (What cannot move on here is the board's to say: its "Can't move on here".)"""
    from apps.dashboard.words import status_words
    from apps.pipeline.models import DesignTask
    groups = []
    for status in WAITING:
        qs = DesignTask.objects.filter(status=status).order_by("-updated_at")
        count = qs.count()
        if not count:
            continue
        groups.append({"words": status_words(status), "count": count,
                       "designs": [(t.pk, _title(t), _cannot_pass(t)) for t in qs[:SHOWN]]})
    working = DesignTask.objects.filter(status__in=WORKING).order_by("updated_at")
    stopped = DesignTask.objects.filter(status__in=("failed", "rejected", "container_stage_visually_rejected"))
    return {
        "groups": groups,
        "working": [(t.pk, _title(t), status_words(t.status), t.updated_at) for t in working[:SHOWN]],
        "working_count": working.count(),
        "stopped": [(t.pk, _title(t), status_words(t.status), (t.error_message or "").strip())
                    for t in stopped.order_by("-updated_at")[:SHOWN]],
        "stopped_count": stopped.count(),
    }


#: what a container's Gate-2 readiness refuses for, in words (§BH55 Phase 3, survey row 4.22) — the one map, which
#: History reads too; a reason not listed there is shown as the record's own code


def _cannot_pass(task) -> str:
    """Why a design that waits for a review cannot pass it — a container's single readiness authority, read here
    (`build_container_gate2_readiness`, derived from the records; it writes nothing)."""
    if task.design_target != "product_container" or task.status != "awaiting_gate_2":
        return ""
    try:
        from apps.pipeline.services.reconstruction_status import build_container_gate2_readiness
        readiness = build_container_gate2_readiness(task)
    except Exception:            # noqa: BLE001 — a reason that cannot be read is not a reason to hide the design
        return ""
    if not readiness or readiness.get("ready"):
        return ""
    from apps.dashboard.words import READINESS_WORDS
    code = str(readiness.get("reason_code") or "")
    return READINESS_WORDS.get(code) or (f"its review is blocked ({code.replace('_', ' ').lower()})" if code
                                         else "its review is blocked")


def targets() -> list[dict]:
    """The targets whose designs cannot be finished at their review, as their cards say, with why."""
    from apps.pipeline.targets import ui
    # [his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line each"] the card no
    # longer carries how a container is finished; Status says it, as the card said it
    return [{"name": c["name"], "status": c["status"],
             "why": "%s %s" % (c["description"], ui.CONTAINER_FINISH) if c["status"] == ui.FINISHED_WHEN_ACCEPTED
             else c["description"]}
            for c in ui.TARGET_CARDS if c["status"] != ui.FINISHED_AT_REVIEW]


def production_gates() -> dict:
    """Gates A to E, DERIVED now from their own records (write=False), and the spec pack's items for B to E."""
    from apps.pipeline.services import production_authority_gates as pag
    from apps.pipeline.services import spec_pack_intake as spi
    intake = spi.validate(write=False)[0]
    record = pag.build(intake=intake, write=False)
    gates = []
    for key, gate in (record.get("gates") or {}).items():
        title = spi.GATE_TITLES.get(key) or "Gate A — the Illustrator file executes"
        gates.append({"key": key, "title": title, "state": gate.get("state"),
                      "passed": gate.get("state") == "PASSED",
                      "requires": gate.get("requires") or [], "cause": gate.get("cause") or "",
                      "missing": gate.get("items_missing"), "total": gate.get("items_total"),
                      "passed_at": gate.get("passed_at") or "",
                      "passed_by": "the owner" if gate.get("passed_by") == "PROJECT_OWNER" else gate.get("passed_by") or ""})
    items = [{"gate": spi.GATE_TITLES.get(i["gate"], i["gate"]), "item": i["item"], "state": i["state"],
              "when": i.get("satisfies_when") or ""} for i in intake.get("items") or []]
    return {"gates": gates, "items": items, "passed": record.get("gates_passed"),
            "packaging_may_begin_now": record.get("packaging_may_begin_now"),
            "wait_on": record.get("gates_b_to_e_wait_on") or ""}


def spending() -> dict:
    """Spend on the refusal's own clock — the rolling 24 hours — against the daily cap; this month by provider and
    model; the designs that spent most against their own cap; and what the ledger does not count."""
    from django.db.models import Count, Sum
    from django.utils import timezone

    from apps.pipeline.models import ApiCallRecord, DesignTask
    from apps.pipeline.services.cost_ledger import day_cost_usd
    now = timezone.now()
    month = ApiCallRecord.objects.filter(created_at__gte=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    by_model = [{"provider": r["provider"], "model": r["model"], "calls": r["calls"], "usd": float(r["usd"] or 0)}
                for r in month.values("provider", "model").annotate(usd=Sum("cost_usd"), calls=Count("id"))
                .order_by("-usd")]
    per_task = list(ApiCallRecord.objects.exclude(task=None).values("task_id").annotate(usd=Sum("cost_usd"))
                    .order_by("-usd")[:SHOWN])
    titles = {t.pk: _title(t) for t in DesignTask.objects.filter(pk__in=[r["task_id"] for r in per_task])}
    cap_task = float(settings.MAX_COST_PER_TASK)
    last24 = float(day_cost_usd())
    cap_day = float(settings.MAX_COST_PER_DAY)
    return {
        "last24": last24, "cap_day": cap_day, "left": max(0.0, cap_day - last24), "over": last24 >= cap_day,
        "month": sum(r["usd"] for r in by_model), "by_model": by_model, "cap_task": cap_task,
        "per_task": [{"pk": r["task_id"], "title": titles.get(r["task_id"], ""), "usd": float(r["usd"] or 0),
                      "over": float(r["usd"] or 0) > cap_task} for r in per_task],
        "not_counted": NOT_COUNTED,
    }


def _commit_at(utc) -> str:
    """The commit that was HEAD when a verdict was given — derived: the newest commit no later than its time."""
    import subprocess
    if not utc:
        return ""
    try:
        out = subprocess.run(["git", "log", "-1", "--until", str(utc), "--format=%h"], cwd=str(settings.BASE_DIR),
                             capture_output=True, text=True, timeout=5, check=False)
        return out.stdout.strip()
    except (OSError, ValueError):       # a machine without git says nothing, and the verdict still shows
        return ""


def record_gates() -> dict:
    """What the last gates said: the suite's word (GREEN / AMBER / REFUSE) and the record-integrity ledger's rows."""
    base = Path(settings.BASE_DIR)
    suite = {}
    try:
        suite = json.loads((base / ".suite_gate_result").read_text())
    except (OSError, ValueError):
        pass
    # §BH55 Phase 3 (survey row 4.18): the record carries the time, not the commit — the commit is DERIVED here as the
    # newest one no later than that time, which is the tree the suite read (a gate runs before its own commit is made)
    at = _commit_at(suite.get("utc"))
    tier2 = suite.get("tier2")
    if not tier2:
        try:
            m = re.search(r"TIER_2=(\w+)", (base / ".tier2_gate_output").read_text())
            tier2 = m.group(1) if m else None
        except OSError:
            tier2 = None
    rows = []
    try:
        with open(base / "docs" / "roadmap" / "palt_m6" / "record_gate_ledger.jsonl", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return {"tier2": tier2, "tier2_words": TIER2_WORDS.get(tier2 or "", ""), "suite_utc": _when(suite.get("utc")),
            "at": at,
            "running": bool(suite) and not tier2,
            "ledger_total": len(rows), "ledger_refused": sum(1 for r in rows if r.get("verdict") != "OK"),
            "ledger_last": [{"utc": _when(r.get("utc")), "ok": r.get("verdict") == "OK", "checked": r.get("records_checked"),
                             "refusals": r.get("refusal_count")} for r in rows[-5:]][::-1]}


def _when(iso) -> str:
    """A record's time in words — "26 September 2026, 02:14 UTC" — never an ISO stamp; what does not parse, as written."""
    from datetime import datetime
    try:
        at = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return str(iso or "")
    return at.strftime("%-d %B %Y, %H:%M UTC")


def brain() -> dict | None:
    """When the brain — the index of the rulings, the queue and the records — was last rebuilt, and whether it still
    matches the files it was built from: its own record lists every source with its hash, and each is read and hashed
    here (§BH55 Phase 3, survey rows 4.5 and 5.1). Read-only; the measurement is cached for five minutes, and a source
    named relatively is read under the repository's root, where the rebuild wrote it from."""
    try:
        d = json.loads((Path(settings.BASE_DIR).resolve().parent / "var" / "brain" / "freshness.json").read_text())
    except (OSError, ValueError):
        return None
    out = {"built_at": d.get("built_at") or "", "sources": d.get("source_count")}
    out.update(_brain_freshness(d))
    return out


def _brain_freshness(record: dict) -> dict:
    """Each source of the brain's own record, read and hashed against the hash the rebuild wrote."""
    import hashlib

    from django.core.cache import cache
    cached = cache.get(_FRESHNESS_KEY)
    if cached is not None:
        return cached
    root = Path(settings.BASE_DIR).resolve().parent
    changed, missing = [], []
    sources = record.get("sources") or {}
    for name, digest in sources.items():
        path = Path(name)
        path = path if path.is_absolute() else root / path
        try:
            measured = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            missing.append(Path(name).name)
            continue
        if measured != digest:
            changed.append(Path(name).name)
    out = {"measured": len(sources), "fresh": not changed and not missing,
           "changed": sorted(changed)[:8], "changed_count": len(changed),
           "missing": sorted(missing)[:8], "missing_count": len(missing)}
    cache.set(_FRESHNESS_KEY, out, 300)
    return out


def providers() -> dict:
    """Which provider keys are set — never their values — and the last pre-spend verdict this system recorded
    (§BH55 Phase 3, survey row 1.16). The verdict is an AgentLog row the image producer writes before it spends
    (provider_prespend.persist_prespend); nothing here calls a provider."""
    from apps.pipeline.models import AgentLog
    keys = [{"name": "Anthropic", "set": bool(settings.ANTHROPIC_API_KEY),
             "words": "plans the directions, writes the prompts, checks the concepts and translates the label copy"},
            {"name": "OpenAI", "set": bool(settings.OPENAI_API_KEY),
             "words": "draws every concept"}]
    row = (AgentLog.objects.filter(action__startswith="Provider pre-spend validation")
           .order_by("-timestamp").first())
    last = None
    if row is not None:
        detail = ((row.payload or {}).get("prespend") or {}) if isinstance(row.payload, dict) else {}
        last = {"when": row.timestamp, "passed": "PASSED" in (row.action or ""), "design": row.task_id,
                "codes": [str(c) for c in (detail.get("codes") or [])]}
    return {"keys": keys, "last": last}


def launch_checks() -> list[dict]:
    """The conditions `verify_launch` prints, read here without touching anything — the keys, debug, the brand and
    what it carries (§BH55 Phase 3, survey row 7.13). The queue and the worker are the health probe's, not this list's."""
    from apps.core.models import Brand, ColorSystem, Product
    brand = Brand.objects.first()
    products = Product.objects.filter(brand=brand).count() if brand else 0
    systems = ColorSystem.objects.filter(brand=brand, status="canonical").count() if brand else 0
    return [
        {"name": "The planner's key", "ok": bool(settings.ANTHROPIC_API_KEY),
         "words": "set" if settings.ANTHROPIC_API_KEY else "not set — the planning, the prompts and the checks refuse"},
        {"name": "The drawing key", "ok": bool(settings.OPENAI_API_KEY),
         "words": "set" if settings.OPENAI_API_KEY else "not set — no concept can be drawn"},
        {"name": "The database", "ok": bool(settings.DATABASES.get("default", {}).get("NAME")),
         "words": "set up" if settings.DATABASES.get("default", {}).get("NAME") else "not configured",
         "record": settings.DATABASES.get("default", {}).get("NAME") or ""},       # its name, one click under
        {"name": "Debug mode", "ok": not settings.DEBUG,
         "words": "off, as a live machine wants it" if not settings.DEBUG else "ON — a live machine wants it off"},
        {"name": "A brand on record", "ok": bool(brand), "words": brand.name if brand else "none — seed one first"},
        {"name": "Its products", "ok": products > 0, "words": f"{products} on record"},
        {"name": "Its colour systems", "ok": systems > 0, "words": f"{systems} agreed"},
    ]


def materials_record() -> dict | None:
    """The materials record's counts, as the Materials page reads it (materials_library.tier_rows)."""
    from apps.dashboard import materials_library as ml
    rows = ml.tier_rows()
    if rows is None:
        return None
    placeable = sum(1 for r in rows if r.get("tier") == "PRODUCTION")
    return {"rows": len(rows), "placeable": placeable, "reference": len(rows) - placeable}


def suite_extent() -> dict | None:
    """The test suite's declared extent — its manifest's files and its floor of tests."""
    try:
        m = json.loads((Path(settings.BASE_DIR) / "docs" / "roadmap" / "palt_m6" / "suite_file_manifest.json")
                       .read_text())
    except (OSError, ValueError):
        return None
    return {"files": len(m.get("files") or []), "floor": m.get("total_floor"),
            "declared": str(m.get("generated") or "")[:10]}


def health(probe: bool = False) -> dict:
    """The database and its migrations always; the queue, the worker and the worker's revision only when asked."""
    from apps.core import health as h
    from apps.pipeline.services.revision import current_revision
    out = {"db": h.check_db(), "migrations": h.migration_state(), "web_revision": current_revision(),
           "eager": bool(settings.CELERY_TASK_ALWAYS_EAGER), "probed": probe}
    if probe and not out["eager"]:
        out["redis"] = h.check_redis()
        out["worker"] = bool(h.ping_workers())
        out["worker_revision"] = None
        if out["worker"]:
            try:
                from apps.pipeline.tasks import report_worker_revision
                out["worker_revision"] = str(report_worker_revision.delay().get(timeout=5))
            except Exception:  # noqa: BLE001 — a probe that does not answer is said, never raised
                out["worker_revision"] = None
        out["same_revision"] = bool(out["worker_revision"]) and out["worker_revision"] == out["web_revision"]
    return out


#: a programme record's states, in words
PROGRAMME_WORDS = {
    "OWNER_ACCEPTED_CLOSED": "accepted by the owner, and closed",
    "STARTED_VQ2_A1_PENDING_OWNER_REVIEW": "started — its first artwork waits on the owner's review",
    "UNBLOCKED_PENDING_EXPLICIT_START": "free to start — waiting for the owner to start it",
    "BLOCKED_PENDING_SUPPLIER_EVIDENCE": "blocked — it waits on the spec pack the owner hands over (§BH46)",
    "REVISION_REQUIRED": "revision required",
    "BASELINE_AND_ARCHITECTURE": "a baseline and its architecture",
    "PENDING_PROGRAM_ARCHITECTURE_REVIEW": "its architecture waits on the owner's review",
    "VQ1_OWNER_ACCEPTED": "accepted by the owner",
    "VQ1_STRUCTURAL_GEOMETRY_ACCEPTED": "its structural geometry accepted",
    "VQ1_WORKSTREAM_CLOSED": "its workstream closed",
}


def _said(value) -> str:
    return PROGRAMME_WORDS.get(str(value or ""), str(value or "").replace("_", " ").lower())


def programme() -> dict:
    """The visual-quality programme, read from its records. It stood on the home as a sentence fixed in the template —
    "VQ-1 / CORR-2..CORR-5 all REJECTED" — which its own records contradict: the owner accepted VQ-1's final structural
    candidate and closed its workstream (vq1_owner_acceptance.json)."""
    base = Path(settings.BASE_DIR) / "docs"

    def load(rel):
        try:
            return json.loads((base / rel).read_text())
        except (OSError, ValueError):
            return {}
    acc = load("visual_quality/vq1_master/vq1_owner_acceptance.json")
    ws = load("visual_quality/vq1_master/vq1_workstream_state.json")
    rev = load("visual_quality/vq1/vq1_human_structural_review.json")
    prog = load("complete_product/final_visual_quality_program.json")
    return {
        "accepted_on": acc.get("created_at") or "",
        "accepted_by": "the owner" if acc.get("decided_by") == "PROJECT_OWNER" else acc.get("decided_by") or "",
        "accepted_words": "; ".join(_said(c) for c in acc.get("codes") or []),
        "workstreams": [(label, _said(ws.get(key))) for key, label in (
            ("VQ_1", "VQ-1, the bottle's structure"), ("VQ_2", "VQ-2, its artwork"), ("VQ_3", "VQ-3"),
            ("PRODUCTION_GEOMETRY", "Production geometry")) if ws.get(key)],
        "review_state": _said(rev.get("state")), "review_on": rev.get("decided_at") or "",
        "status": _said(prog.get("status")), "architecture": _said(prog.get("human_review_state")),
        "scorecard": [(k.replace("_", " "), v.get("max"), v.get("critical_min"))
                      for k, v in (prog.get("scorecard") or {}).items() if isinstance(v, dict)],
    }
