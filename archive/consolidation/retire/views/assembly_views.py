"""Versioned countertop geometry; no concept generation or approval endpoints."""
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
from apps.pipeline.services.assembly_spec import BACKEND, PIN_HASH, digest, facts, make_assembly, validate_assembly
from apps.pipeline.services.assembly_output import FILES, compile_bundle, is_assembly, source_artifact
from apps.ire.stepped_display import solve

CREATION_SALT = "stepped-assembly-create-v1"
EXAMPLE_ROOT = Path(settings.BASE_DIR).parent / "docs/audit/day-3"

class AssemblyForm(forms.Form):
    case = forms.ChoiceField(label="Brief", choices=[("family-proposal","Separate taller family proposal"),("144","Original Ginkgo Mist brief · 144"),("146","Original Kiss Me brief · 146")])
    width = forms.FloatField(label="Overall width (mm)", min_value=50,max_value=1000)
    depth = forms.FloatField(label="Overall depth (mm)", min_value=50,max_value=1000)
    height = forms.FloatField(label="Overall height (mm)", min_value=50,max_value=1000)
    riser = forms.FloatField(label="Fixed row rise (mm); leave empty to solve",min_value=1,max_value=200,required=False)
    expected_hash = forms.CharField(required=False,widget=forms.HiddenInput)
    creation_token = forms.CharField(required=False,widget=forms.HiddenInput)

def _member(user,write=False):
    if not user_has_role(user,*(ROLE_DESIGNER,ROLE_ADMIN) if write else ALL_ROLES):
        raise PermissionDenied

def _record(folder):
    record=json.loads((folder/"build-record.json").read_text())
    validate_assembly(record["assembly_spec"],expected_hash=record["spec_hash"])
    return record

@login_required
@require_http_methods(["GET","POST"])
def master(request,task_id=None):
    _member(request.user,write=request.method=="POST")
    task=get_object_or_404(DesignTask,pk=task_id) if task_id is not None else None
    if task and not is_assembly(task):raise Http404
    current=task.current_output() if task else None
    revisions=list(task.packaging_outputs.order_by("-pk")) if task else []
    output=current
    if task and request.GET.get("revision"):
        output=next((r for r in revisions if str(r.pk)==request.GET["revision"]),None)
        if output is None:raise Http404
    record=output.spec_sheet if output else _record(EXAMPLE_ROOT/"master")
    spec=validate_assembly(record["assembly_spec"],expected_hash=record["spec_hash"])
    model=solve(spec)
    initial=dict(case=spec.case_id.value,width=spec.envelope_requested.width_mm.value,
                 depth=spec.envelope_requested.depth_mm.value,height=spec.envelope_requested.height_mm.value,
                 riser=spec.rules.fixed_riser_mm.value,expected_hash=(task.options or {}).get("current_spec_hash","") if task else "",
                 creation_token=signing.dumps({"user":request.user.pk,"nonce":uuid.uuid4().hex},salt=CREATION_SALT) if not task else "")
    form=AssemblyForm(request.POST if request.method=="POST" else None,initial=initial)
    code=200
    if request.method=="POST" and form.is_valid():
        try: saved=save_revision(request.user,task_id,form.cleaned_data)
        except (ValueError,signing.BadSignature) as exc:
            form.add_error(None,str(exc));code=409 if "newer revision" in str(exc) or "already used" in str(exc) else 400
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Assembly compilation failed")
            form.add_error(None,"The new drawing could not be built. Your earlier revision is unchanged.");code=503
        else:return redirect("dashboard:assembly_master_task",task_id=saved.pk)
    elif request.method=="POST":code=400
    def url(role):
        return reverse("dashboard:assembly_file",args=[output.pk,role]) if output else reverse("dashboard:assembly_example",args=["family-proposal",role])
    cases=[]
    for case in ("144","146"):
        result=solve(make_assembly(case))
        cases.append(dict(case=case,**result))
    return render(request,"dashboard/assembly_master.html",dict(task=task,output=output,revisions=revisions,
        form=form,model=model,spec_hash=record["spec_hash"],pin=PIN_HASH,
        picture=url("comparison"),package=url("package"),cases=cases,
        views=[dict(name=n.title(),url=url(n)) for n in ("plan","front","side","section","isometric")],
        numbers=[dict(field=p,**f) for p,f in facts(spec.model_dump()) if isinstance(f["value"],(int,float)) or f["authority"]=="unresolved"],
        can_edit=(output==current and user_has_role(request.user,ROLE_DESIGNER,ROLE_ADMIN))),status=code)

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
                submission_hash = digest({key: values[key] for key in ("case", "width", "depth", "height", "riser")})
                task = DesignTask.objects.filter(created_by=user, options__assembly_creation_key=creation_key).first()
                if task:
                    if task.options.get("assembly_submission_hash") != submission_hash:
                        raise ValueError("This creation form was already used with different copy. Open the saved master and create a new revision.")
                    return task
                brand = Brand.objects.filter(name__iexact="BBROSE").first()
                if brand is None:
                    raise ValueError("The BBROSE brand record is missing; this template cannot be used for another brand.")
                previous_hash, revision = None, 1
            else:
                task = DesignTask.objects.select_for_update().get(pk=task_id)
                if not is_assembly(task):
                    raise ValueError("This is not an authored stand master.")
                previous_hash = task.options["current_spec_hash"]
                if values["expected_hash"] != previous_hash:
                    raise ValueError("A newer revision exists. Reload the page before making another revision.")
                revision = task.options["current_revision"] + 1
            case = values["case"]
            dims = (float(values["width"]), float(values["depth"]), float(values["height"]))
            original = {"144": (180.,150.,300.), "146": (120.,120.,260.)}
            if case in original and dims != original[case]:
                raise ValueError("The original brief's envelope cannot be changed. Choose the separate family proposal for a new envelope.")
            spec = make_assembly(case, revision=revision, parent_hash=previous_hash,
                                 dimensions=dims if case == "family-proposal" else None,
                                 riser=float(values["riser"]) if values.get("riser") else None)
            with tempfile.TemporaryDirectory(dir=staging_root) as work:
                staged = Path(work) / "master"
                record = compile_bundle(spec.model_dump(), staged)
                if task_id is None:
                    task = DesignTask.objects.create(brand=brand, created_by=user, task_text=spec.source_brief.value,
                            design_target="display_stand", status="awaiting_gate_2",
                            options={"authoring_backend": BACKEND, "assembly_creation_key": creation_key,
                                     "assembly_submission_hash": submission_hash,
                                     "spend_held": True})
                relative = Path("dielines/hybrid/assemblies") / str(task.pk) / f"r{revision}-{record['spec_hash'][:16]}"
                published = media / relative
                if published.exists():
                    published = None
                    raise ValueError("This immutable revision directory already exists; it will not be replaced.")
                published.parent.mkdir(parents=True, exist_ok=True)
                staged.rename(published)
                record["artifact_root"] = relative.as_posix()
                image = GeneratedImage.objects.create(task=task, direction_name="Stand geometry — provisional",
                    direction_id="stepped-display", prompt_used="Deterministic AssemblySpec geometry; no image provider.",
                    image_file=(relative / "comparison.png").as_posix(), is_approved=False, qa_passed=False,
                    reference_provenance={"kind": "authored_master_snapshot", "spec_hash": record["spec_hash"],
                                          "source_pin": spec.product.model_dump()})
                PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet=record,
                    design_preview=(relative / "comparison.png").as_posix())
                task.options = dict(task.options, current_spec_hash=record["spec_hash"], current_revision=revision)
                task.status = "awaiting_gate_2"
                task.save(update_fields=["options", "status", "updated_at"])
                AgentLog.objects.create(task=task, agent_name="Assembly", actor=user,
                    action=f"Authored stand revision {revision} saved; geometry only; physical review pending. No provider calls.")
        return task
    except Exception:
        # Only this newly created, unpublished directory may be cleaned up.
        if published is not None and published.exists():
            shutil.rmtree(published)
        raise


def artifact_path(output,role):
    if role not in FILES or not is_assembly(output.task):raise Http404
    record=output.spec_sheet
    validate_assembly(record["assembly_spec"],expected_hash=record["spec_hash"])
    root=(Path(settings.MEDIA_ROOT)/"dielines/hybrid/assemblies"/str(output.task_id)).resolve()
    path=(Path(settings.MEDIA_ROOT)/record["artifact_root"]/FILES[role][0]).resolve()
    if not path.is_relative_to(root) or not path.is_file() or digest(path.read_bytes())!=record["artifact_hashes"].get(path.name):raise Http404
    return path

@login_required
@require_GET
def artifact(request,output_id,role):
    _member(request.user)
    output=get_object_or_404(PackagingOutput.objects.select_related("task"),pk=output_id)
    try:path=artifact_path(output,role)
    except (ValueError,KeyError,OSError):raise Http404
    return FileResponse(path.open("rb"),content_type=FILES[role][1],as_attachment=role not in ("comparison","plan","front","side","section","isometric"),filename=path.name)

@login_required
@require_GET
def example(request,case,role):
    _member(request.user)
    if case not in ("family-proposal","144","146") or role not in FILES:raise Http404
    folder=EXAMPLE_ROOT/("master" if case=="family-proposal" else "case-"+case)
    try:
        record=_record(folder);path=folder/FILES[role][0]
        if digest(path.read_bytes())!=record["artifact_hashes"].get(path.name):raise Http404
    except (ValueError,KeyError,OSError):raise Http404
    return FileResponse(path.open("rb"),content_type=FILES[role][1],as_attachment=role not in ("comparison","plan","front","side","section","isometric"),filename=path.name)

@login_required
@require_GET
def pinned_serum(request):
    _member(request.user)
    try:path=source_artifact("comparison-at-100-percent.pdf")
    except (ValueError,KeyError,OSError):raise Http404
    return FileResponse(path.open("rb"),content_type="application/pdf",filename=path.name)
