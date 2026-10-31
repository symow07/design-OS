"""Immutable assembly publication; every drawing derives from one validated spec."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .assembly_spec import BACKEND, PIN_ROOT, digest, validate_assembly
from apps.ire.stepped_display import solve
from apps.ire.assembly_drawings import emit

FILES = {"comparison":("comparison.png","image/png"),"drawing":("drawing-set.pdf","application/pdf"),
         "plan_pdf":("plan-at-100-percent.pdf","application/pdf"),"package":("assembly-package.zip","application/zip"),
         "spec":("assembly-spec.json","application/json"),"preflight":("assembly-preflight.json","application/json"),
         **{k:(k+'.svg','image/svg+xml') for k in ('plan','front','side','section','isometric','comparison_svg')}}
FILES['comparison_svg']=('comparison.svg','image/svg+xml')


def is_assembly(task):
    return (task.options or {}).get('authoring_backend')==BACKEND


def compile_bundle(data,output):
    spec=validate_assembly(data);folder=Path(output)
    folder.mkdir(parents=True,exist_ok=False)
    model=solve(spec)
    def save(name,obj):
        (folder/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    save('assembly-spec.json',spec.model_dump());save('assembly-model.json',model)
    counts=emit(spec,model,folder)
    preflight=dict(schema_version='assembly_preflight/1.0',status=model['status'],spec_hash=digest(spec.model_dump()),
                   solver_inputs=spec.model_dump(),solver_outputs=model,exported_instance_counts=counts,
                   sightline_table=model['sightline_table'],unresolved=model['unresolved'],
                   production_ready=False,no_load_claim=True,artwork_bound=False,native_ai='not_requested_day3',
                   source_note='A conservative full-width opaque-row sightline bound; exact fixed eye, no sampled pass.',
                   next_step='Day 4 item 1: concept147 fidelity serum master; then new assembly revision for artwork and sightlines.')
    save('assembly-preflight.json',preflight)
    (folder/'READ-ME.txt').write_text('PROVISIONAL ASSEMBLY / NOT A PRODUCTION RELEASE\n\n'+
        ('SOLUTION within the declared conservative template.\n' if model['status']=='solution_provisional' else 'REFUSED: drawings are diagnostic geometry, not an accepted solution.\n')+
        '\n'.join(model['refusal_reasons'])+'\n\nPrint plan-at-100-percent.pdf at 100%, no Fit to page. Check the 50 mm bar.\n'+
        'Comparison uses scale 1:2 for every view. SVGs and PDF contain vector geometry and twelve tagged instances per view.\n'+
        'Seat elevation means bottle bottom. Solid seats carry bottles; separate oversized-hole collars locate them.\n'+
        '6 mm board and all joints are provisional. No load, tip, supplier or creative approval is claimed.\n'+
        'Day 2 composition is superseded. Only the family proposal and brief 144 use its pinned geometry for the sightline test. Brief 146 uses its separate declared vial and has no resolved decoration region or sightline result. No artwork was inherited.\n')
    with zipfile.ZipFile(folder/'assembly-package.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.suffix!='.zip':archive.write(path,path.name)
    record=dict(backend=BACKEND,assembly_spec=spec.model_dump(),spec_hash=digest(spec.model_dump()),
                preflight=preflight,artifact_hashes={p.name:digest(p.read_bytes()) for p in folder.iterdir() if p.is_file()},
                creative_acceptance='not_requested_geometry_only',production_ready=False)
    save('build-record.json',record)
    return record


def source_artifact(name):
    from .assembly_spec import load_pin
    _,record,_=load_pin()
    if name not in record['artifact_hashes']:
        raise ValueError('Unknown pinned source artifact.')
    path=(PIN_ROOT/name).resolve()
    if path.parent!=PIN_ROOT.resolve() or digest(path.read_bytes())!=record['artifact_hashes'][name]:
        raise ValueError('Pinned source artifact changed.')
    return path
