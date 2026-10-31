"""Bounded serum authoring: local proofs, immutable revisions, no paid calls."""
from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.models import Brand
from apps.pipeline.models import AgentLog, DesignTask, GeneratedImage, PackagingOutput
from apps.pipeline.permissions import ALL_ROLES, ROLE_ADMIN, ROLE_DESIGNER, user_has_role
from apps.pipeline.services.design_spec import BACKEND, DEFAULT_COPY, DesignSpec, digest, make_spec
from apps.pipeline.services.hybrid_bottle_output import compile_bundle, is_hybrid

FILES = {"comparison": ("comparison.png", "image/png"), "artwork": ("artwork.png", "image/png"),
         "proof": ("comparison-at-100-percent.pdf", "application/pdf"),
         "pdf": ("artwork.pdf", "application/pdf"), "ai": ("artwork-pdf-compatible.ai", "application/pdf"),
         "svg": ("artwork.svg", "image/svg+xml"), "package": ("editable-master.zip", "application/zip"),
         "preflight": ("preflight.json", "application/json")}
CREATION_SALT = "hybrid-serum-create-v1"


class MasterForm(forms.Form):
    name = forms.CharField(label="Product name (up to two lines)", max_length=80, strip=False, widget=forms.Textarea(attrs={"rows": 2}))
    descriptor = forms.CharField(label="Product type", max_length=60, strip=False)
    benefit = forms.CharField(label="Benefit line", max_length=120, strip=False)
    care = forms.CharField(label="Supporting copy", max_length=120, strip=False)
    arabic = forms.CharField(label="Arabic copy", max_length=120, strip=False, widget=forms.TextInput(attrs={"dir": "rtl"}))
    volume = forms.CharField(label="Volume line", max_length=60, strip=False)
    method = forms.ChoiceField(label="Proposed decoration method", choices=[("unresolved", "Not decided"), ("screen_print", "Screen print"), ("label", "Label")])
    height_datum = forms.ChoiceField(label="What does the 108 mm height include?", choices=[("unresolved", "Unknown — keep provisional"), ("overall", "Bottle including cap")])
    dominant = forms.RegexField(r"^#[0-9a-fA-F]{6}$", label="Main field colour", widget=forms.TextInput(attrs={"type": "color"}))
    secondary = forms.RegexField(r"^#[0-9a-fA-F]{6}$", label="Lettering colour", widget=forms.TextInput(attrs={"type": "color"}))
    accent = forms.RegexField(r"^#[0-9a-fA-F]{6}$", label="Accent rule colour", widget=forms.TextInput(attrs={"type": "color"}))
    expected_hash = forms.CharField(required=False, widget=forms.HiddenInput)
    creation_token = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean(self):
        data = super().clean()
        # HTML form transport uses CRLF for textarea line breaks. Preserve the
        # logical lines in the master; no copy words or spaces are removed.
        for key in DEFAULT_COPY:
            if key in data:
                data[key] = data[key].replace("\r\n", "\n").replace("\r", "\n")
        return data


def _member(user, write=False):
    if not user_has_role(user, *(ROLE_DESIGNER, ROLE_ADMIN) if write else ALL_ROLES):
        raise PermissionDenied


def _task(task_id):
    task = get_object_or_404(DesignTask, pk=task_id)
    if not is_hybrid(task):
        raise Http404
    return task


def _initial(spec=None, current_hash="", token=""):
    return {**(spec["copy"] if spec else DEFAULT_COPY), "method": spec["surface"]["method"] if spec else "unresolved",
            "height_datum": spec["stock"]["height_datum"] if spec else "unresolved",
            **(spec["palette"] if spec else {"dominant": "#F6F1E7", "secondary": "#172A35", "accent": "#B45C0A"}),
            "expected_hash": current_hash, "creation_token": token}


@login_required
@require_http_methods(["GET", "POST"])
def master(request, task_id=None):
    _member(request.user, write=request.method == "POST")
    if not getattr(settings, "HYBRID_BOTTLE_ENABLED", False):
        raise Http404
    task = _task(task_id) if task_id is not None else None
    output = task.current_output() if task else None
    form = MasterForm(request.POST if request.method == "POST" else None, initial=_initial(
        (output.spec_sheet or {}).get("design_spec") if output else None,
        (task.options or {}).get("current_spec_hash", "") if task else "",
        signing.dumps({"user": request.user.pk, "nonce": uuid.uuid4().hex}, salt=CREATION_SALT) if task is None else ""))
    code = 200
    if request.method == "POST" and form.is_valid():
        try:
            task = save_revision(request.user, task_id, form.cleaned_data)
        except (ValueError, signing.BadSignature) as exc:
            form.add_error(None, str(exc))
            code = 409 if "newer revision" in str(exc) or "already used" in str(exc) else 400
        except Exception:
            # Keep the old master and all entered strings. Operator traceback stays in the log.
            import logging
            logging.getLogger(__name__).exception("Hybrid master compilation failed")
            form.add_error(None, "The new proof could not be built. Your previous revision is unchanged; your entered copy is kept below.")
            code = 503
        else:
            return redirect("dashboard:hybrid_master_task", task_id=task.pk)
    elif request.method == "POST":
        code = 400
    revisions = list(task.packaging_outputs.order_by("-pk")) if task else []
    selected = output
    if task and request.GET.get("revision"):
        selected = next((o for o in revisions if str(o.pk) == request.GET["revision"]), None)
        if selected is None:
            raise Http404
    preview = reverse("dashboard:hybrid_file", args=[selected.pk, "comparison"]) if selected else reverse("dashboard:hybrid_example", args=["comparison"])
    return render(request, "dashboard/hybrid_master.html", dict(form=form, task=task, output=selected,
                  revisions=revisions, preview_url=preview, can_edit=(selected == output and user_has_role(request.user, ROLE_DESIGNER, ROLE_ADMIN)),
                  pending=(selected.spec_sheet["preflight"]["unresolved"] if selected else [])), status=code)


def save_revision(user, task_id, values):
    """One local compile at a time per author/task. Nothing overwrites an old revision."""
    _member(user, write=True)
    media = Path(settings.MEDIA_ROOT)
    staging_root = media / "dielines/hybrid/.staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    published = None
    try:
        with transaction.atomic():
            if task_id is None:
                identity = signing.loads(values["creation_token"], salt=CREATION_SALT, max_age=86400)
                if identity.get("user") != user.pk or not identity.get("nonce"):
                    raise ValueError("This creation form belongs to another session. Open a new form.")
                get_user_model().objects.select_for_update().get(pk=user.pk)
                creation_key = digest(identity)
                submission_hash = digest({key: values[key] for key in (*DEFAULT_COPY, "height_datum", "method", "dominant", "secondary", "accent")})
                task = DesignTask.objects.filter(created_by=user, options__hybrid_creation_key=creation_key).first()
                if task:
                    if task.options.get("hybrid_submission_hash") != submission_hash:
                        raise ValueError("This creation form was already used with different copy. Open the saved master and create a new revision.")
                    return task
                brand = Brand.objects.filter(name__iexact="BBROSE").first()
                if brand is None:
                    raise ValueError("The BBROSE brand record is missing; this template cannot be used for another brand.")
                previous_hash, revision = None, 1
            else:
                task = DesignTask.objects.select_for_update().get(pk=task_id)
                if not is_hybrid(task):
                    raise ValueError("This is not an authored serum master.")
                previous_hash = task.options["current_spec_hash"]
                if values["expected_hash"] != previous_hash:
                    raise ValueError("A newer revision exists. Reload the page before making another revision.")
                revision = task.options["current_revision"] + 1
            spec = make_spec(copy={k: values[k] for k in DEFAULT_COPY}, height_datum=values["height_datum"],
                             method=values["method"], revision=revision, parent_hash=previous_hash,
                             palette={k: values[k] for k in ("dominant", "secondary", "accent")})
            with tempfile.TemporaryDirectory(dir=staging_root) as work:
                staged = Path(work) / "master"
                record = compile_bundle(spec.model_dump(), staged)
                if task_id is None:
                    task = DesignTask.objects.create(brand=brand, created_by=user, task_text=spec.brief,
                            design_target="product_container", status="awaiting_gate_2",
                            options={"authoring_backend": BACKEND, "hybrid_creation_key": creation_key,
                                     "hybrid_submission_hash": submission_hash,
                                     "spend_held": True})
                relative = Path("dielines/hybrid") / str(task.pk) / f"r{revision}-{record['spec_hash'][:16]}"
                published = media / relative
                if published.exists():
                    published = None
                    raise ValueError("This immutable revision directory already exists; it will not be replaced.")
                published.parent.mkdir(parents=True, exist_ok=True)
                staged.rename(published)
                record["artifact_root"] = relative.as_posix()
                image = GeneratedImage.objects.create(task=task, direction_name="Authored master snapshot — review pending",
                    direction_id=spec.direction_id, prompt_used="Locally authored from DesignSpec; no image provider.",
                    image_file=(relative / "artwork.png").as_posix(), is_approved=False, qa_passed=False,
                    reference_provenance={"kind": "authored_master_snapshot", "spec_hash": record["spec_hash"],
                                          "assets": [a.model_dump() for a in spec.assets]})
                PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet=record,
                    design_preview=(relative / "comparison.png").as_posix(),
                    design_preview_ai=(relative / "artwork-pdf-compatible.ai").as_posix())
                task.options = dict(task.options, current_spec_hash=record["spec_hash"], current_revision=revision)
                task.status = "awaiting_gate_2"
                task.save(update_fields=["options", "status", "updated_at"])
                AgentLog.objects.create(task=task, agent_name="Hybrid", actor=user,
                    action=f"Authored serum revision {revision} saved; creative and supplier review pending. No provider calls.")
        return task
    except Exception:
        # Only this newly created, unpublished directory may be cleaned up.
        if published is not None and published.exists():
            shutil.rmtree(published)
        raise


def artifact_path(output, role):
    if role not in FILES or not is_hybrid(output.task):
        raise Http404
    record = output.spec_sheet
    DesignSpec.model_validate(record["design_spec"])
    if digest(record["design_spec"]) != record["spec_hash"]:
        raise Http404
    root = (Path(settings.MEDIA_ROOT) / "dielines/hybrid" / str(output.task_id)).resolve()
    path = (Path(settings.MEDIA_ROOT) / record["artifact_root"] / FILES[role][0]).resolve()
    if not path.is_relative_to(root) or not path.is_file() or digest(path.read_bytes()) != record["artifact_hashes"].get(path.name):
        raise Http404
    return path


@login_required
@require_GET
def artifact(request, output_id, role):
    _member(request.user)
    output = get_object_or_404(PackagingOutput.objects.select_related("task"), pk=output_id)
    try:
        path = artifact_path(output, role)
    except (ValueError, KeyError):
        raise Http404
    return FileResponse(path.open("rb"), content_type=FILES[role][1],
                        as_attachment=role not in ("comparison", "artwork"), filename=path.name)


@login_required
@require_GET
def example(request, role):
    _member(request.user)
    if role not in FILES:
        raise Http404
    root = Path(settings.BASE_DIR).parent / "docs/audit/day-2/master"
    path = root / FILES[role][0]
    if not path.is_file():
        raise Http404
    return FileResponse(path.open("rb"), content_type=FILES[role][1],
                        as_attachment=role not in ("comparison", "artwork"), filename=path.name)
