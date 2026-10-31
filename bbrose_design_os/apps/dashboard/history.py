"""§BH52(b) SLICE 1 — HISTORY: a read model over the database rows, never a directory listing.

MEDIA_ROOT holds hundreds of thousands of files no row names (test leftovers among them), so everything this module
shows starts from a row. It writes nothing: no save, create, update or delete; it calls no GET that writes (the
spec-sheet download, the concept-reference list and thumbnail, the palette intent page, the notification
preferences) and no audit-writing enforcement.

A file is linked through the authenticated path that already exists, ``/files/<path>`` (apps/core/views.py:11-28),
only when its stored name resolves to a file under MEDIA_ROOT and outside the REFERENCE-class directories. A name
that resolves outside MEDIA_ROOT is withheld with that reason; a missing file says so.

Tier: each linked file's sha256 is joined to the tier record (the outer
var/design_intelligence/audits/dip0/tiers/materials_tiers.jsonl, read only). A row's tier is shown where one exists
and "no tier row" where none does; neither is permission to place anything.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

from django.conf import settings

from apps.dashboard.words import (            # §BH55 Phase 3: the one place the screen's words live
    MATERIAL_STUDY_WORDS, acceptance_warning_rows, decision_words, gate_words, operation_words, production_note_words,
    readiness_words, reference_words, status_words, target_words, stop_words, tier_words,
)
from apps.pipeline.models import (
    TASK_STATUS, ApiCallRecord, ConceptReference, CreativeBrief, DesignProject, DesignTask, Gate1RegenerationJob,
    Notification, PackagingOutput, PaletteIntentConfirmation, PaletteMaterialArtifact,
)

#: Directories whose bytes are REFERENCE-class by origin: third-party web bodies, rasters of materials files, and
#: rasters of the materials' historical designs. History links none of them, whatever a row names.
REFERENCE_CLASS_DIRS = ("web_quarantine", "concept_thumbs", "references")
#: §BH54(b): the door refuses a file that lies under one of these folders, by the same predicate — REFUSED by name
#: with this code. The predicate reads the RESOLVED path and compares directory IDENTITY (os.path.samefile) with each
#: folder that exists, falling back to the spelled name: this volume is case-insensitive, and a typed
#: "WEB_QUARANTINE/…" reaches the same bytes as "web_quarantine/…".
REFUSED_REFERENCE_FOLDER = "REFUSED_REFERENCE_FOLDER"


def reference_folder(resolved: Path, root: Path):
    """The canonical REFERENCE-class folder a resolved path under ``root`` lies in, or None — decided by directory
    identity where the folder exists on disk, by the spelled first component where it does not."""
    try:
        rel = resolved.relative_to(root)
    except ValueError:
        return None
    if not rel.parts:
        return None
    head = root / rel.parts[0]
    for name in REFERENCE_CLASS_DIRS:
        folder = root / name
        try:
            if folder.is_dir() and head.exists() and os.path.samefile(head, folder):
                return name
        except OSError:
            pass
        if rel.parts[0] == name:
            return name
    return None

LINKED = "LINKED"
MISSING = "MISSING — no file at the stored name"
WITHHELD_ESCAPES = "WITHHELD — the stored name resolves outside MEDIA_ROOT"
WITHHELD_REFERENCE = "WITHHELD — a REFERENCE-class directory; history never serves its bytes"
NO_TIER_ROW = "no tier row"

INLINE_KINDS = {".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image", ".gif": "image",
                ".svg": "image", ".pdf": "pdf"}
FILE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".pdf", ".ai", ".json", ".jsx", ".zip")
STATUS_LABELS = dict(TASK_STATUS)          # the model's own labels — the screen reads words.py instead
DIRECTORY_LIMIT = 500


def media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def tier_record_path() -> Path:
    """The materials tier record — WHICH governed file may be placed in a design, and on whose grant.

    §BH55 Phase 4 ("the untracked tier record"): it lived under var/, which .gitignore ignores whole, so the record
    that decides placement rights was in no commit and a fresh clone had none. It is tracked evidence now, beside the
    caption record §BH43(a) tracked (docs/design_intelligence/). The ignored copy is read only where the tracked one
    is absent — a partial checkout, or a machine that still holds the audit's own output.
    """
    configured = getattr(settings, "HISTORY_TIER_RECORD", None)
    if configured:
        return Path(configured)
    root = Path(settings.BASE_DIR).resolve().parent
    tracked = root / "docs" / "design_intelligence" / "tiers" / "materials_tiers.jsonl"
    if tracked.exists():
        return tracked
    return (root / "var" / "design_intelligence" / "audits" / "dip0"
            / "tiers" / "materials_tiers.jsonl")


_lock = threading.Lock()
_tiers = {"key": None, "by_sha": {}}
_hashes: dict = {}


def tiers_by_sha() -> dict:
    """sha256 -> the tiers the record gives it; a sha the record gives two tiers keeps both."""
    path = tier_record_path()
    try:
        stat = path.stat()
    except OSError:
        return {}
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    with _lock:
        if _tiers["key"] != key:
            found: dict = {}
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if row.get("sha256") and row.get("tier"):
                        found.setdefault(row["sha256"], set()).add(row["tier"])
            _tiers["key"], _tiers["by_sha"] = key, {k: sorted(v) for k, v in found.items()}
        return _tiers["by_sha"]


def sha256_of(path: Path) -> str:
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key not in _hashes:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
        _hashes[key] = digest.hexdigest()
    return _hashes[key]


def tier_of(path: Path) -> str:
    found = tiers_by_sha().get(sha256_of(path))
    return " + ".join(found) if found else NO_TIER_ROW


def media_file(name, label="", bases=()) -> dict:
    """A stored file name as history shows it: linked through /files/, missing, or withheld with its reason.

    ``bases`` are the directories a record names its files against (a dieline job's directory, a rejection
    record's ``dir``). An absolute stored path is taken as it stands; a stored ``/files/`` URL is read as its path.
    Every candidate must resolve under MEDIA_ROOT.
    """
    name = str(name or "")
    if name.startswith("/files/"):
        name = name[len("/files/"):]
    shown = {"label": label, "name": name, "state": MISSING, "url": None, "kind": "download", "tier": None,
             "tier_words": tier_words(None)}      # §BH55 Phase 3: what the materials record says of it, in words
    if not name:
        return shown
    root = media_root()
    raw = Path(name)
    candidates = [raw] if raw.is_absolute() else [root / raw] + [root / b / raw for b in bases if b]
    escaped = False
    for candidate in candidates:
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            escaped = True
            continue
        rel = resolved.relative_to(root)
        if reference_folder(resolved, root) is not None:      # §BH54(b): one predicate for history and the door
            shown["state"] = WITHHELD_REFERENCE
            return shown
        if resolved.is_file():
            tier = tier_of(resolved)
            shown.update(state=LINKED, url="/files/" + quote(rel.as_posix()),
                         kind=INLINE_KINDS.get(resolved.suffix.lower(), "download"),
                         tier=tier, tier_words=tier_words(tier))      # §BH55 Phase 3: the record's tier, in words
            return shown
    if escaped:
        shown["state"] = WITHHELD_ESCAPES
    return shown


def directory_files(dirname, label) -> list:
    """The files under a directory a record names (a rejection's ``dir`` or ``artifact_dir``), bounded to MEDIA_ROOT."""
    root = media_root()
    raw = Path(str(dirname or ""))
    resolved = (raw if raw.is_absolute() else root / raw).resolve()
    if not str(dirname or "") or not resolved.is_relative_to(root) or not resolved.is_dir():
        return []
    if len(resolved.relative_to(root).parts) < 2:            # a record's own directory, never a whole media tree
        return []
    found = []
    for p in sorted(resolved.rglob("*")):
        if p.is_file():
            found.append(media_file(str(p.relative_to(root)), label))
            if len(found) == DIRECTORY_LIMIT:
                break
    return found


def _dedupe(files) -> list:
    seen, out = set(), []
    for f in files:
        if f["name"] and f["name"] not in seen:
            seen.add(f["name"])
            out.append(f)
    return out


def _named_files(value, label="", bases=()) -> list:
    """Every string in a record that names a file, as history shows it."""
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            found += _named_files(v, str(k), bases)
    elif isinstance(value, list):
        for v in value:
            found += _named_files(v, label, bases)
    elif isinstance(value, str) and value.lower().endswith(FILE_SUFFIXES) and "\n" not in value:
        found.append(media_file(value, label, bases))
    return found


# ------------------------------------------------------------------------------------------------ the rejections

def rejections(output: PackagingOutput) -> list:
    """Each rejection record an output's spec sheet keeps, with its codes, who decided, when, and its files."""
    spec = output.spec_sheet or {}
    job_dir = "dielines/%s" % output.dieline_job_id if output.dieline_job_id else ""
    shown = []
    for key in sorted(k for k in spec if k.startswith("container_reconstruction_rejected")):
        rec = spec.get(key) or {}
        shown.append({"key": key, "label": rec.get("label") or rec.get("state") or "",
                      "codes": rec.get("codes") or [],
                      "by": rec.get("decided_by") or rec.get("rejected_by") or "",
                      "at": rec.get("decided_at") or rec.get("rejected_at") or "",
                      "note": rec.get("invalidation") or rec.get("preserved") or "",
                      "files": _dedupe([media_file((rec.get("rejected_output") or {}).get(k), k)
                                        for k in ("design_preview", "design_preview_ai")
                                        if (rec.get("rejected_output") or {}).get(k)])})
    for i, rec in enumerate(spec.get("rejected_outputs") or []):
        if not isinstance(rec, dict):
            continue
        bases = [b for b in (rec.get("dir"), job_dir) if b]
        files = _named_files(rec.get("files") or {}, "", bases)
        for d in (rec.get("dir"), rec.get("artifact_dir")):
            files += directory_files(d, "in the record's directory")
        shown.append({"key": "rejected_outputs[%d]" % i, "label": rec.get("label") or "",
                      "codes": rec.get("codes") or [], "by": rec.get("decided_by") or "",
                      "at": rec.get("recorded_at") or "", "note": rec.get("note") or rec.get("reason") or "",
                      "files": _dedupe(files)})
    return shown


# ----------------------------------------------------------------------------------------------------- the list

def _search_text(task: DesignTask) -> str:
    parts = [task.task_text, task.design_target, task.status, STATUS_LABELS.get(task.status, ""),
             task.product.name if task.product else ""]
    brief = CreativeBrief.objects.filter(task=task).first()
    if brief:
        parts += [json.dumps(brief.directions, ensure_ascii=False), json.dumps(brief.design_intent, ensure_ascii=False)]
    for im in task.images.all():
        parts += [im.direction_name, im.prompt_used, im.user_rejection_label, im.qa_notes]
    parts += [d.notes for d in task.gate_decisions.all()]
    parts += [log.action for log in task.logs.all()]
    for output in task.packaging_outputs.all():
        for rej in rejections(output):
            parts += [rej["key"], rej["label"], rej["note"], " ".join(map(str, rej["codes"]))]
    return "\n".join(p for p in parts if p).lower()


def _has_rejections(task: DesignTask) -> bool:
    return (task.gate_decisions.filter(decision="reject").exists()
            or any(rejections(o) for o in task.packaging_outputs.all()))


def _cover(task: DesignTask):
    image = (task.images.filter(is_approved=True).order_by("-created_at").first()
             or task.images.order_by("-created_at").first())
    return media_file(image.image_file.name, "concept") if image and image.image_file else None


def task_list(params, user=None) -> dict:
    """Every past task, with no cap, searched and filtered from its rows, ordered by date — narrowed, when asked, to one
    brand or to the designs this account started (the old dashboard's brand switch and "Mine", reached again: the
    checklist of 2026-09-26)."""
    q = (params.get("q") or "").strip()
    order = "oldest" if params.get("order") == "oldest" else "newest"
    tasks = DesignTask.objects.select_related("product", "brand").order_by(
        "created_at" if order == "oldest" else "-created_at", "id")
    if params.get("target"):
        tasks = tasks.filter(design_target=params["target"])
    if params.get("status"):
        tasks = tasks.filter(status=params["status"])
    if (params.get("product") or "").isdigit():
        tasks = tasks.filter(product_id=int(params["product"]))
    if (params.get("brand") or "").isdigit():
        tasks = tasks.filter(brand_id=int(params["brand"]))
    if params.get("mine") == "1" and user is not None:
        tasks = tasks.filter(created_by=user)
    if params.get("from"):
        tasks = tasks.filter(created_at__date__gte=params["from"])
    if params.get("to"):
        tasks = tasks.filter(created_at__date__lte=params["to"])
    rows = []
    for task in tasks:
        outputs = list(task.packaging_outputs.all())
        has_renders = any(o.design_preview or o.design_preview_ai for o in outputs)
        if params.get("renders") == "1" and not has_renders:
            continue
        if params.get("rejections") == "1" and not _has_rejections(task):
            continue
        if q and q.lower() not in _search_text(task):
            continue
        rows.append({"task": task, "status_label": status_words(task.status),        # §BH55 Phase 3: the words
                     "target_label": target_words(task.design_target),
                     "brief_start": (task.task_text or "")[:200],
                     "brief_more": len(task.task_text or "") > 200, "cover": _cover(task),
                     "images": task.images.count(), "outputs": len(outputs),
                     "decisions": task.gate_decisions.count(), "logs": task.logs.count(),
                     "has_renders": has_renders})
    from apps.core.models import Product
    return {"rows": rows, "q": q, "order": order, "params": params, "total": DesignTask.objects.count(),
            "statuses": [(value, status_words(value)) for value, _ in TASK_STATUS],
            "targets": [(t, target_words(t))
                        for t in sorted(set(DesignTask.objects.values_list("design_target", flat=True)))],
            "products": Product.objects.filter(pk__in=DesignTask.objects.values("product_id")).order_by("name")}


# ------------------------------------------------------------------------------------------------------ one task

def _pretty(value) -> str:
    return json.dumps(value, indent=1, ensure_ascii=False, sort_keys=True, default=str)


def spec_records(spec) -> list:
    """Every top-level record of a spec sheet, labelled by its key, the raw record beside it."""
    shown = []
    for key in sorted(spec or {}):
        value = spec[key]
        if isinstance(value, dict):
            state = next((f"{k}: {value[k]}" for k in ("status", "state", "schema_version")
                          if k in value and not isinstance(value[k], (dict, list))), "")
            summary = state or "%d keys" % len(value)
        elif isinstance(value, list):
            summary = "%d items" % len(value)
        else:
            summary = str(value)[:160]
        shown.append({"key": key, "summary": summary, "raw": _pretty(value), "words": record_words(key)})
    return shown


def record_words(key) -> str:
    """A technical record's name in words — "container_design_graph/2.0" reads "Design graph (version 2.0)" — the
    record's own key kept beside it, one click under (the owner's goal of 2026-09-25, (d))."""
    name, _, version = str(key).partition("/")
    words = name.removeprefix("container_").replace("_", " ").strip().capitalize() or str(key)
    return f"{words} (version {version})" if version else words


def _checks_date(output) -> str:
    """§BH50(g)(4): the record-side date of the spec's checks (the reconstruction's own log, else the resume request,
    else the output row's creation, which is the begin-output time and says so)."""
    from apps.pipeline.models import AgentLog
    log = (AgentLog.objects.filter(task=output.task, agent_name="ARIA", action__contains="reached Gate 2")
           .order_by("-timestamp").first())
    if log is not None:
        return log.timestamp.strftime("%Y-%m-%d %H:%MZ") + " (the reconstruction's 'reached Gate 2' log)"
    resume = ((output.spec_sheet or {}).get("container_resume") or {}).get("requested_at")
    if resume:
        return str(resume)[:16] + " (container_resume.requested_at)"
    return output.created_at.strftime("%Y-%m-%d %H:%MZ") + " (the output row's creation — the begin-output time)"


def readiness_read(output) -> dict:
    """§BH50(g)(4): the Gate-2 reader's own verdict and the stale mark, derived at readiness-read from the saved spec —
    the same functions the board and Gate 2 read; nothing persisted, nothing rewritten."""
    from apps.dashboard.owner_channel import preview_sha256
    from apps.ire.container_production_readiness import UNCONFIRMED_WARNINGS, build_readiness, spec_staleness
    spec = (output.spec_sheet if output is not None else None) or {}
    if not spec.get("container_reconstruction"):
        return {"applies": False}
    verdict = build_readiness(spec, preview_sha256(output)[0])      # §BH71: his acceptance, for this picture
    return {"applies": True, "blocking": list(verdict["blocking_codes"]),
            # §BH55 Phase 3: each blocking code in words, with the code itself beside it — this is the record's page
            "blocking_words": [{"code": c, "words": readiness_words(c)} for c in verdict["blocking_codes"]],
            # the owner's answer of 2026-09-27: the maker's printing specification, shown as production notes
            "notes": list(verdict["production_notes"]),
            "note_words": [{"code": c, "words": production_note_words(c)} for c in verdict["production_notes"]],
            # §BH71 (0a): what is not measured yet — a warning beside Approve, never a reason it is refused
            "warnings": list(verdict["acceptance_warnings"]),
            "warning_words": [r for r in acceptance_warning_rows(verdict["acceptance_warnings"])
                              if r["code"] not in UNCONFIRMED_WARNINGS],
            # [his answer of 2026-09-29 to the §BH71 report, (4)] words the executor wrote that nobody has confirmed,
            # said apart from the checks not measured yet
            "unconfirmed_words": [r for r in acceptance_warning_rows(verdict["acceptance_warnings"])
                                  if r["code"] in UNCONFIRMED_WARNINGS],
            # §BH71: an acceptance given for an earlier picture, said as what it is
            "human": ("given for an earlier picture, so it counts for nothing now"
                      if verdict["human_design_acceptance_state"] == "VOID"
                      else verdict["human_design_acceptance_state"]),
            "staleness": spec_staleness(spec), "checks_date": _checks_date(output)}


def output_view(output: PackagingOutput) -> dict:
    spec = output.spec_sheet or {}
    job_dir = "dielines/%s" % output.dieline_job_id if output.dieline_job_id else ""
    files = [media_file(output.design_preview.name, "current render (preview)"),
             media_file(output.design_preview_ai.name, "current render (.ai)"),
             media_file(output.dieline_file.name, "dieline (SVG)"),
             media_file(output.dieline_ai_file.name, "dieline (.ai)"),
             media_file(output.production_pdf.name, "production PDF (CMYK)"),
             media_file(output.spec_pdf.name, "spec sheet PDF")]
    for key in ("structural_comparison_pdf", "structural_checklist"):
        if spec.get(key):
            files.append(media_file(spec[key], key.replace("_", " "), [job_dir]))
    handoff = []
    for key in ("handoff", "container_handoff"):
        if spec.get(key):
            handoff += _named_files((spec[key] or {}).get("files") or {}, key)
    artifacts = (spec.get("structure_presentation") or {}).get("provisional_artifacts") or {}
    provisional = ([media_file(url, name) for name, url in sorted(artifacts.items())] if isinstance(artifacts, dict)
                   else _named_files(artifacts))
    return {"output": output, "files": [f for f in files if f["name"]], "rejections": rejections(output),
            "handoff": _dedupe(handoff), "provisional": _dedupe(provisional), "records": spec_records(spec),
            "readiness": readiness_read(output),          # §BH50(g)(4)
            "no_preview": not output.design_preview}


def quality_words(image) -> str:
    """What the check said of one concept — the design page's own rule: a check that never ran is not a failure."""
    try:
        notes = json.loads(image.qa_notes) if image.qa_notes else {}
    except (TypeError, ValueError):
        notes = {}
    score = notes.get("score") if isinstance(notes, dict) else None
    if score in (None, ""):
        return "Quality not checked"
    return f"Quality {score}/10 — {'passes the check' if image.qa_passed else 'below the check'}"


def task_view(task: DesignTask, user) -> dict:
    brief = CreativeBrief.objects.filter(task=task).first()
    calls = list(ApiCallRecord.objects.filter(task=task).order_by("created_at"))
    from apps.pipeline.feed_words import said, who
    return {
        # §BH55 Phase 3: a past design reads as the live one does — its state, its kind, its decisions, its references,
        # its notifications, its spending and its log, each in words, with the record's own codes beside them
        "task": task, "status_label": status_words(task.status), "target_label": target_words(task.design_target),
        "brief": brief,
        # why it stopped, in the words every screen uses; the error as recorded, folded beneath (the owner's goal (d))
        "stop_words": stop_words(task) if task.error_message else "",
        "direction_name": next((str(d.get("name") or "") for d in ((brief.directions or []) if brief else [])
                                if isinstance(d, dict) and d.get("direction_id") == brief.selected_direction_id), ""),
        "directions": _pretty(brief.directions) if brief else "",
        "intent": _pretty(brief.design_intent) if brief and brief.design_intent else "",
        "images": [{"image": im, "quality": quality_words(im),
                    "file": media_file(im.image_file.name, "concept") if im.image_file else None,
                    "provenance": _pretty(im.reference_provenance) if im.reference_provenance else ""}
                   for im in task.images.order_by("created_at", "variation_number")],
        "outputs": [output_view(o) for o in task.packaging_outputs.select_related("dieline_job").order_by("created_at")],
        "decisions": [{"row": d, "gate": gate_words(d.gate), "decision": decision_words(d.decision)}
                      for d in task.gate_decisions.select_related("decided_by").order_by("decided_at")],
        "logs": [{"log": log, "payload": _pretty(log.payload) if log.payload is not None else "",
                  "who": who(log.agent_name), "said": said(log.action)}
                 for log in task.logs.select_related("actor").order_by("timestamp", "id")],
        "references": [{"row": r, **reference_words(r)}
                       for r in ConceptReference.objects.filter(task=task).order_by("created_at", "id")],
        "jobs": [{"job": j, "prompts": _pretty(j.prompts_payload) if j.prompts_payload else "",
                  # the direction it drew for, by name (the old record page printed its id: the checklist, 2026-09-26)
                  "direction": next((str(d.get("name") or "") for d in ((brief.directions or []) if brief else [])
                                     if isinstance(d, dict) and d.get("direction_id") == j.direction_id), "")}
                 for j in Gate1RegenerationJob.objects.filter(task=task).order_by("created_at")],
        "confirmations": [{"row": c, "intent": _pretty(c.confirmed_intent)}
                          for c in PaletteIntentConfirmation.objects.filter(task=task).order_by("created_at")],
        "material_artifacts": [{"row": a, "words": MATERIAL_STUDY_WORDS.get(a.variant_name, a.variant_name)}
                               for a in PaletteMaterialArtifact.objects.filter(task=task).order_by("created_at")],
        "notifications": [{"row": n, "words": status_words(n.kind)}
                          for n in Notification.objects.filter(task=task, recipient=user).order_by("created_at")],
        "calls": [{"row": c, "did": operation_words(c.operation)} for c in calls],
        "spend": sum((c.cost_usd for c in calls), Decimal("0")),
    }


# ------------------------------------------------------------------------------------------- projects and jobs

def project_view(project: DesignProject) -> dict:
    from apps.pipeline.targets.composite import build_project_summary
    summary = build_project_summary(project)
    stages = [{k: v for k, v in stage.items() if k not in ("hero_url", "deliverables")}
              for stage in summary.get("stages", [])]
    # §BH50(g)(4): the snapshot the summary reads is what a run persisted (none of the outputs carries one today);
    # the reader's own verdict is derived beside it, per stage, from the stage's first output
    for stage in stages:
        first = (PackagingOutput.objects.filter(task_id=stage["task_id"]).order_by("created_at").first()
                 if stage.get("task_id") else None)
        stage["derived"] = readiness_read(first) if first is not None else {"applies": False}
    return {"project": project, "summary": {k: v for k, v in summary.items() if k != "stages"}, "stages": stages,
            "metadata": [{"key": k, "raw": _pretty(v)} for k, v in sorted((project.metadata or {}).items())],
            "tasks": list(project.tasks.order_by("created_at"))}


def dieline_jobs() -> list:
    from apps.dielines.models import DielineJob
    shown = []
    for job in DielineJob.objects.select_related("product").order_by("-created_at"):
        outputs = list(PackagingOutput.objects.filter(dieline_job=job).values_list("task_id", flat=True))
        files = [media_file(p, label) for p, label in ((job.svg_output_path, "SVG"), (job.ai_output_path, ".ai"),
                                                       (job.pdf_output_path, "PDF")) if p]
        shown.append({"job": job, "tasks": outputs, "files": files, "selection": _pretty(job.structure_selection),
                      "warnings": _pretty(job.warnings) if job.warnings else ""})
    return shown


def concept_grid(params) -> list:
    from apps.pipeline.models import GeneratedImage
    images = GeneratedImage.objects.select_related("task").order_by("-created_at", "id")
    if params.get("target"):
        images = images.filter(task__design_target=params["target"])
    return [{"image": im, "file": media_file(im.image_file.name, "concept") if im.image_file else None}
            for im in images]
