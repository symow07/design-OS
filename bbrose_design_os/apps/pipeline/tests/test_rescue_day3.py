"""Owner briefs, conservative visibility, immutable revisions and checked outputs."""
import copy
import json
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import xml.etree.ElementTree as ET

import fitz
import pytest
from django.core import signing
from django.urls import reverse

from apps.pipeline.services.assembly_spec import PIN_HASH, PIN_ROOT, PRESET, digest, make_assembly, validate_assembly
from apps.pipeline.services.assembly_output import compile_bundle
from apps.ire.stepped_display import solve, sightlines, accept_legacy_tray
from apps.ire.assembly_drawings import assert_svg_count

@pytest.fixture(autouse=True)
def local_environment(settings,tmp_path):
    settings.BRAND_MARK_APPROVAL_LOOKUP=True
    settings.MEDIA_ROOT=tmp_path/'media'

@pytest.mark.parametrize('case,dimensions,required', [('144',[180.,150.,300.],410.),('146',[120.,120.,260.],244.),('family-proposal',[180.,150.,420.],410.)])
def test_original_envelopes_and_named_product_reach_every_contract(case,dimensions,required):
    spec=make_assembly(case); model=solve(spec)
    assert model['envelope_requested']==dimensions
    assert model['required_height_mm']==required
    assert len(model['positions'])==12 and len(spec.decks)==3
    assert model['status']==('solution_provisional' if case=='family-proposal' else 'refused')
    assert [p['value'] for p in spec.provenance if p['field']=='rules.eye_front_mm']==[500.]
    assert spec.product.spec_hash.value==(None if case=="146" else PIN_HASH)
    assert spec.product.database_output_id.authority=='unresolved'
    assert spec.product_envelope.filled_mass_g.value is None
    assert set(p['id']['value'] for p in spec.print_surfaces)=={'header.front','header.back','riser.1.front','riser.2.front','riser.3.front','side.left','side.right','base.front','lip.front'}
    assert all(p['copy_slots']['value']==[] and p['required_languages']['value']==['EN','AR'] for p in spec.print_surfaces)
    if case=='146':
        assert spec.product_envelope.profile.value=='square'
        assert spec.holes.requested_size_mm.value==18.
        assert all(row['visible_fraction_lower_bound'] is None for row in model['sightline_table'])
        assert all(p['product_spec_hash'] is None for p in model['positions'])
    elif case=='144':
        assert any('110 mm' in r for r in model['refusal_reasons'])
        assert 'رذاذ الوجه' in json.dumps(spec.required_copy_by_surface.value,ensure_ascii=False)

@pytest.mark.parametrize('mutation',[
 lambda d:d['count'].update(value=8),
 lambda d:d['product']['spec_hash'].update(value='0'*64),
 lambda d:d['product']['artifact_hashes']['value'].update({'design-spec.json':'0'*64}),
 lambda d:d['product_envelope']['cap_width_mm'].update(value=1000.),
 lambda d:d['product_envelope']['decoration_bottom_mm'].update(value=100.),
 lambda d:d['product_envelope']['height_datum'].update(value='overall',authority='owner_provided'),
 lambda d:d['rules']['thickness_mm'].update(value=6.,authority='owner_provided'),
 lambda d:d['rules']['eye_front_mm'].update(value=1000.),
 lambda d:d['decks'][0]['seat_elevation_mm'].update(value=42.),
 lambda d:d.update(decks=[]),
 lambda d:d['count'].update(authority='proposed'),
 lambda d:d['print_surfaces'][0]['copy_slots'].update(value=['silently bound']),
 lambda d:d.update(parent_hash='0'*64),
 lambda d:d.update(schema_version='assembly_spec/99'),
 lambda d:d['envelope_requested']['height_mm'].update(value=float('nan')),
])
def test_corrupt_pin_geometry_provenance_and_derived_fields_refused(mutation):
    data=make_assembly().model_dump();mutation(data)
    with pytest.raises(ValueError):validate_assembly(data)


def test_original_brief_cannot_be_resized_by_compiler_and_equivalent_inputs_normalise():
    with pytest.raises(ValueError,match='Original brief'):make_assembly('144',dimensions=(180.,150.,420.))
    assert make_assembly('144',dimensions=(180.,150.,300.)).model_dump()==make_assembly('144').model_dump()
    assert make_assembly(hole=31.).model_dump()==make_assembly().model_dump()

@pytest.mark.parametrize('kwargs,failed',[({'hole':29.},'clearance'),({'dimensions':(100.,100.,200.)},'width'),({'riser':20.},'sightline'),({'hole':50.,'dimensions':(220.,178.,420.)},'depth'),({'dimensions':(1000.,150.,420.)},'sightline')])
def test_adversarial_geometry_is_a_refusal(kwargs,failed):
    model=solve(make_assembly(**kwargs))
    assert model['status']=='refused'
    assert not next(c['passed'] for c in model['checks'] if c['check']==failed)


def test_full_visibility_bound_covers_surface_not_only_centres():
    spec=make_assembly();model=solve(spec);assert model['uniform_rise_mm']==98.
    assert [d['seat_elevation_mm']['value'] for d in model['decks']]==[6.,104.,202.]
    assert all(r['passed'] and r['visible_fraction_lower_bound']==1. for r in model['sightline_table'])
    # Independent dense ray calculations corroborate, but do not certify, the
    # analytic bound. Surface arc endpoints and all intervening angles tested.
    eye=(90.,-500.,350.);radius=14.5
    for target in model['positions']:
        for n in range(65):
            theta=-16/radius+32/radius*n/64
            px=target['x_mm']+radius*math.sin(theta)
            py=target['y_mm']-radius*math.cos(theta)
            pz=target['z_mm']+7.
            assert (eye[0]-px)*math.sin(theta)+(eye[1]-py)*(-math.cos(theta))>0
            for row in range(1,target['row']):
                front=next(p for p in model['positions'] if p['row']==row)
                yy=front['y_mm']+radius
                z=eye[2]+(pz-eye[2])*(yy-eye[1])/(py-eye[1])
                assert z>=front['z_mm']+108.+.25-1e-8
    assert not all(r['passed'] for r in sightlines(spec,[6.,103.,200.],model['tread_mm']))


def test_changed_pinned_bytes_refuse_without_rebinding(monkeypatch,tmp_path):
    from apps.pipeline.services import assembly_spec as module
    import shutil
    target=tmp_path/'pin';shutil.copytree(PIN_ROOT,target)
    monkeypatch.setattr(module,'PIN_ROOT',target)
    (target/'comparison.png').write_bytes(b'changed')
    with pytest.raises(ValueError,match='pinned serum artifact'):make_assembly()


def test_actual_legacy_flat_structure_export_is_refused(tmp_path):
    from apps.pipeline.targets.artwork import DisplayStandTarget
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    brief=json.loads((PRESET/'original-briefs.json').read_text())['144']
    task=SimpleNamespace(task_text=brief,product=None)
    route=DisplayStandTarget();fit=route.fit_for(task)
    extra=route.extras_for(task,fit)[0]
    doc=extra['document']();path=tmp_path/'legacy-flat-144.pdf';emit_pdf_ai(doc,str(path))
    assert path.is_file() and len(fitz.open(path))>=1
    result=accept_legacy_tray(fit)
    assert result['status']=='refused' and len(result['reasons'])==3
    assert fit['unit']['width_mm']!=29. # actual old fallback, not accepted by new route

@pytest.mark.parametrize('number',[11,13])
def test_export_count_negative_controls(number,tmp_path):
    groups=''.join(f'<g data-view="plan" data-bottle-id="b{i}"><polygon points="0,0 1,0 1,1"/></g>' for i in range(number))
    path=tmp_path/'bad.svg';path.write_text('<svg>'+groups+'</svg>')
    with pytest.raises(ValueError,match='Export count'):assert_svg_count(path)


def test_real_bundle_counts_dimensions_and_calibration_without_providers(tmp_path,monkeypatch):
    from apps.pipeline.services import claude_service
    monkeypatch.setattr(claude_service,'call_claude',Mock(side_effect=AssertionError('Provider called')))
    root=tmp_path/'master';record=compile_bundle(make_assembly().model_dump(),root)
    assert not record['production_ready']
    assert all(n==12 for view in record['preflight']['exported_instance_counts'].values() for n in view.values())
    for name,sha in record['artifact_hashes'].items():assert digest((root/name).read_bytes())==sha
    with fitz.open(root/'plan-at-100-percent.pdf') as pdf:
        assert '50 mm calibration bar' in pdf[0].get_text()
        assert pdf[0].rect.width*25.4/72==pytest.approx(420,abs=.001)
        bars=[d for d in pdf[0].get_drawings() if abs(d['rect'].width*25.4/72-50)<.001 and d['rect'].height==0]
        assert bars
    for kwargs in ({'dimensions':(600.,400.,600.)},{'dimensions':(100.,100.,200.)}):
        # Refused geometry can still be a truthful, unclipped diagnostic sheet.
        compile_bundle(make_assembly(**kwargs).model_dump(),tmp_path/('wide' if kwargs['dimensions'][0]>100 else 'small'))

@pytest.fixture
def author(db,client):
    from django.contrib.auth.models import User
    from apps.core.models import Brand
    user=User.objects.create_superuser('day3-author',password='test-only');Brand.objects.create(name='BBROSE');client.force_login(user);return user


def test_legacy_target_direct_call_refuses_before_work():
    from apps.pipeline.targets.artwork import DisplayStandTarget
    task=SimpleNamespace(options={'authoring_backend':'hybrid_assembly'})
    with pytest.raises(ValueError,match='legacy artwork'):DisplayStandTarget().begin_output(SimpleNamespace(task=task),None)
