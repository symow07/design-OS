"""Day 6 native-route contracts: validation logic on synthetic censuses, glyph multisets, the bbox convention, the outlined-copy negative.

Pure: no database, no Illustrator. Fonts come from the tracked static brand faces.
"""
import json
from collections import Counter
from pathlib import Path
import fitz,numpy as np,pytest
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import mm
from apps.pipeline.services import day6_native as dn,day6_text_audit as da,traced_text as tt,fidelity_master as fm,fidelity_assets as fa

TITLE=fm.FONTS['title']
FIELD={'start_mm':[0,0],'end_mm':[40,0],'stops':[{'offset':0,'srgb':[10,20,30]},{'offset':.5,'srgb':[50,60,70]},{'offset':1,'srgb':[200,210,220]}]}


def make_spec(lines=True):
    runs=[{'text':c,'font_role':'title','x_mm':5+7*i,'baseline_z_mm':8,'scale_x_mm_per_1000pt_unit':.008,'scale_y_mm_per_1000pt_unit':.008} for i,c in enumerate('SUN')]
    graph={'surface_id':'t','width_mm':40,'height_mm':20,'field':FIELD,
           'elements':[{'id':'logo','bbox_mm':[2,2,10,5],'colour_srgb':[255,255,255]},{'id':'name_rule','bbox_mm':[2,6,10,6.4],'colour_srgb':[255,255,255]}],
           'device_roles':[{'role':'CREAM','colour_srgb':[245,219,183],'paths':[{'points_mm':[[30,-5],[50,-5],[50,15],[30,15]],'parent':-1},{'points_mm':[[35,2],[45,2],[45,10],[35,10]],'parent':0}]}],
           'lines':[{'id':'SUN','logical_text':'SUN','colour':[20,20,20],'runs':runs,'measured_bbox_mm':[5,6,25,14]}] if lines else []}
    postscript=fm.font_data('title')['postscript']
    return {'surface_id':'t','graph':graph,'fonts':{'title':{'filename':TITLE.name,'sha256':fa.sha(TITLE),'family':fm.font_data('title')['family'],'postscript':postscript}}}


def make_census(spec,**over):
    postscript=spec['fonts']['title']['postscript']
    frames=[{'name':f'SUN-{i}','text':r['text'],'characters':[{'text':r['text'],'font':postscript,'size':5.7,'horizontal_scale':100,'vertical_scale':100}],
             'bounds':[0,0,1,1],'hidden':False,'opacity':100,'layer':'LIVE TYPE','layer_visible':True} for line in spec['graph']['lines'] for i,r in enumerate(line['runs'])]
    census={'frames':frames,'text_frames':len(frames),'layers':[{'name':n} for n in ('LOGO','LIVE TYPE','RULES','DEVICE','FIELD')],
            'gradient':{'type':'GradientType.LINEAR','name':'D1 FIELD','stops':[{'ramp_point':0,'mid_point':50,'srgb':[10,20,30]},{'ramp_point':50,'mid_point':50,'srgb':[50,60,70]},{'ramp_point':100,'mid_point':50,'srgb':[200,210,220]}],'origin':[0,0],'angle':0,'length':1},
            'compound_paths':[{'name':'CREAM','subpaths':2,'evenodd':True,'srgb':[245,219,183],'layer':'DEVICE'},{'name':'','subpaths':2,'evenodd':False,'srgb':[0,0,0],'layer':'LOGO'}],
            'groups':[{'name':'DEVICE (clipped to face)','clipped':True,'page_items':2,'layer':'DEVICE'},{'name':dn.LOGO_NAME,'clipped':False,'page_items':3,'layer':'LOGO'}],
            'rules':[{'name':'name_rule','srgb':[255,255,255],'bounds':[0,0,1,1]}],'rasters':0,'placed':0,'paths':9,'artboards':1,'artboard':[0,56.7,113.4,0],'colour_space':'DocumentColorSpace.RGB'}
    census.update(over);return census


def test_matching_census_passes_every_structural_check():
    spec=make_spec();checks,details=dn.census_checks(spec,make_census(spec))
    assert checks and all(checks.values()),checks
    assert details['glyphs']['expected_count']==3 and details['device']['found_subpaths']=={'CREAM':2}


def test_glyph_multiset_reports_missing_and_swapped_font():
    spec=make_spec();census=make_census(spec)
    census['frames'][0]['characters'][0]['font']='Helvetica';del census['frames'][2]
    checks,details=dn.census_checks(spec,census)
    assert not checks['glyph_multiset_matched'] and not checks['fonts_matched']
    assert details['glyphs']['missing']==[{'text':'N','font':spec['fonts']['title']['postscript'],'count':1},{'text':'S','font':spec['fonts']['title']['postscript'],'count':1}]
    assert details['glyphs']['unexpected']==[{'text':'S','font':'Helvetica','count':1}]
    assert dn.compare_glyphs(Counter({('a','F'):2}),Counter({('a','F'):2}))['matched']


def test_embedded_raster_or_placed_file_fails_closed():
    spec=make_spec()
    assert not dn.census_checks(spec,make_census(spec,rasters=1))[0]['rasters_zero']
    assert not dn.census_checks(spec,make_census(spec,placed=1))[0]['rasters_zero']
    assert not dn.census_checks(spec,make_census(spec,paths=0))[0]['paths_present']


def test_logo_compound_path_never_counts_as_device():
    spec=make_spec();census=make_census(spec)
    assert dn.census_checks(spec,census)[0]['device_subpaths_matched']
    census['compound_paths'][1]['layer']='DEVICE'
    assert not dn.census_checks(spec,census)[0]['device_subpaths_matched']
    census=make_census(spec);census['compound_paths'][0]['evenodd']=False
    assert not dn.census_checks(spec,census)[0]['device_subpaths_matched']
    census=make_census(spec);census['groups'][0]['clipped']=False
    assert not dn.census_checks(spec,census)[0]['device_clipped_to_face']


def test_gradient_stops_are_measured_not_assumed():
    found=make_census(make_spec())['gradient']
    assert dn.compare_gradient(FIELD,found)['matched']
    found['stops'][1]['srgb']=[53,60,70];result=dn.compare_gradient(FIELD,found)
    assert not result['matched'] and result['max_channel_error']==3
    assert dn.compare_gradient(FIELD,None)['reason'].startswith('no FIELD path')
    short=dict(found,stops=found['stops'][:2]);assert '2 stops read back' in dn.compare_gradient(FIELD,short)['reason']
    radial=dict(found,type='GradientType.RADIAL');radial['stops'][1]['srgb']=[50,60,70];assert not dn.compare_gradient(FIELD,radial)['matched']


def test_bbox_convention_is_upper_left_without_vertical_flip():
    k=600/25.4;shape=(int(20*k)+1,int(40*k)+1)
    r0,r1,c0,c1=dn.pixel_window([10,2,20,6],shape,pad_mm=0)
    assert (c0,c1)==(int(10*k),int(20*k)+1) and (r0,r1)==(int(2*k),int(6*k)+1)
    # the bottle convention (x from the centre line, z from the bottom) converts to the same window
    flat=[10-20,20-6,20-20,20-2]
    assert dn.flat_to_topleft(flat,40,20)==pytest.approx([10,2,20,6])
    assert dn.to_points([0,0],20)==pytest.approx([0,20*dn.MM]) and dn.to_points([40,20],20)==pytest.approx([40*dn.MM,0])
    vector=dn.gradient_vector({'start_mm':[0,20],'end_mm':[40,0]},20)
    assert vector['origin']==pytest.approx([0,0]) and vector['angle']==pytest.approx(np.degrees(np.arctan2(20,40))) and vector['length']==pytest.approx(np.hypot(40,20)*dn.MM)


def test_critical_regions_clip_the_device_to_the_face():
    regions={r['element']:r['bbox_mm'] for r in dn.critical_regions(make_spec()['graph'])}
    assert regions['device.CREAM']==[30,0,40,15] and regions['SUN']==[5,6,25,14] and regions['logo']==[2,2,10,5]


def test_face_without_copy_holds_trivially():
    spec=make_spec(lines=False);checks,details=dn.census_checks(spec,make_census(spec))
    assert checks['glyph_multiset_matched'] and checks['fonts_matched'] and details['fonts']=={'expected':[],'found':[],'matched':True}


def test_validate_marks_an_unexecuted_build_failed(tmp_path):
    (tmp_path/'design-spec.json').write_text(json.dumps(make_spec()))
    result=dn.validate(tmp_path,{'executed':False,'reason':'Adobe Illustrator not available via osascript','saved':False,'reopened':False})
    assert result['passed'] is False and result['failed_checks'][:3]==['native_not_reopened','native_not_saved','illustrator_not_executed']
    assert json.loads((tmp_path/'artwork-native-validation.json').read_text())['reason'].startswith('Adobe Illustrator')


def live_pdf(spec,path):
    g=spec['graph'];canvas=Canvas(str(path),pagesize=(g['width_mm']*mm,g['height_mm']*mm));name='Day6Test-'+fa.sha(TITLE)[:8]
    if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(TITLE)))
    for line in g['lines']:
        canvas.setFillColorRGB(*[v/255 for v in line['colour']])
        for run in line['runs']:
            canvas.saveState();canvas.translate(run['x_mm']*mm,run['baseline_z_mm']*mm);canvas.scale(run['scale_x_mm_per_1000pt_unit']*mm,run['scale_y_mm_per_1000pt_unit']*mm)
            canvas.setFont(name,1000);canvas.drawString(0,0,run['text']);canvas.restoreState()
    canvas.save()


def test_outlined_copy_negative_fails_live_text_while_looking_alike(tmp_path):
    spec=make_spec();source=tmp_path/'live.pdf';live_pdf(spec,source);lines=tt.expected_lines(spec,TITLE.parent)
    assert tt.pdf_live(source,lines)['passed']
    outlined=tmp_path/'outlined.pdf';record=da.outline_copy(source,spec,{'title':TITLE},outlined)
    assert record['runs_outlined']==3 and record['looks_alike'],record
    result=tt.pdf_live(outlined,lines)
    assert not result['passed'] and result['lines'][0]['matched_visible_runs']==0
    with fitz.open(outlined) as doc:
        assert doc[0].get_text().strip()=='' and len(doc[0].get_drawings())>0


def test_text_plane_bakes_only_what_the_text_contributed(tmp_path):
    spec=make_spec();source=tmp_path/'live.pdf';live_pdf(spec,source);lines=tt.expected_lines(spec,TITLE.parent)
    box=tt.pdf_live(source,lines)['lines'][0]['bbox_points'];image,record=da.text_plane(source,box)
    alpha=np.asarray(image)[:,:,3]
    assert record['ppi']==300 and image.size==tuple(record['size_px']) and alpha.max()==255 and (alpha==0).mean()>.5
    with pytest.raises(ValueError):da.text_plane(source,[0,0,2,2])
