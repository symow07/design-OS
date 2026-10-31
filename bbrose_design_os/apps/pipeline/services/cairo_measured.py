"""Choose the heaviest licensed Cairo instance within the owner's ink-box limit."""
from pathlib import Path
import json
import subprocess
import math
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.boundsPen import BoundsPen
from . import fidelity_assets as fa

FONT=fa.APP/'static/fonts/brand2026/Cairo_Variable/Cairo[slnt,wght].ttf'
COPY='سيروم صن ريبير'


def shape(path, weight=None):
    args=['/opt/homebrew/bin/hb-shape',str(path),COPY,'--direction=rtl','--language=ar','--script=arab','--output-format=json']
    if weight is not None:args.append(f'--variations=wght={weight},slnt=0')
    rows=json.loads(subprocess.check_output(args,text=True))
    with TTFont(path) as ft:
        gs=ft.getGlyphSet(location={'wght':weight,'slnt':0} if weight is not None else None)
        cursor=0;boxes=[]
        for row in rows:
            pen=BoundsPen(gs);gs[row['g']].draw(pen)
            row['cursor']=cursor;row['bounds']=pen.bounds
            if pen.bounds:
                a,b,c,d=pen.bounds;boxes.append([a+cursor+row['dx'],b+row['dy'],c+cursor+row['dx'],d+row['dy']])
            cursor+=row['ax']
        bounds=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
        width=(bounds[2]-bounds[0])/(bounds[3]-bounds[1])*25
        return {'rows':rows,'bounds':bounds,'width_at_25px':width,'height_px':25,'delta_width_percent':100*abs(width/155-1),'delta_height_percent':0,'units_per_em':ft['head'].unitsPerEm}


def choose(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    low,high=300.,400.;history=[]
    for _ in range(17):
        middle=(low+high)/2;metric=shape(FONT,middle)
        fits=metric['delta_width_percent']<=3
        history.append({'weight':middle,'width_px':metric['width_at_25px'],'fits':fits})
        if fits:low=middle
        else:high=middle
    chosen=math.floor(low*100)/100
    # Freeze the real static outline, then verify it rather than assuming the variable probe agrees.
    ft=TTFont(FONT);static=instantiateVariableFont(ft,{'wght':chosen,'slnt':0},inplace=False)
    family=f'Cairo D5 {chosen:.2f}';postscript='CairoD5-'+str(chosen).replace('.','_')
    for record in static['name'].names:
        if record.nameID in (1,4,6,16):
            value=postscript if record.nameID==6 else family
            record.string=value.encode(record.getEncoding(),errors='replace')
        elif record.nameID in (2,17):record.string='Regular'.encode(record.getEncoding())
    output=destination/'Cairo-D5-Measured.ttf';static.save(output)
    measured=shape(output)
    if measured['delta_width_percent']>3:raise ValueError('Static instance exceeds measured width tolerance.')
    # Alias shaped GSUB glyphs into the PUA for editable per-glyph transport.
    # Logical copy remains in PDF ActualText, SVG aria-label and native group metadata.
    ft=TTFont(output);aliases={}
    for row in measured['rows']:
        if row['bounds'] is not None and row['g'] not in aliases:aliases[row['g']]=0xE000+len(aliases)
    for table in ft['cmap'].tables:
        if table.isUnicode():table.cmap.update({code:name for name,code in aliases.items()})
    ft.save(output)
    (destination/'OFL.txt').write_bytes((FONT.parent/'OFL.txt').read_bytes())
    measured.update({'chosen_weight':chosen,'next_failing_weight_upper_bound':high,'bisection_resolution':.01,'history':history,'source_font':str(FONT.relative_to(fa.ROOT)),'source_sha256':fa.sha(FONT),'static_font':output.name,'static_sha256':fa.sha(output),'family':family,'postscript':postscript,'glyph_aliases':aliases,'logical_copy':COPY,'transport_limit':'Per-glyph live text with logical line metadata; automatic line reflow is not preserved.','withdrawn_deviation':'ARABIC_SCALE_4_PERCENT: a licensed fitting Cairo instance is now applied, not unavailable.'})
    (destination/'measurement.json').write_text(json.dumps(measured,ensure_ascii=False,indent=2)+'\n')
    return measured


def graph_line(original, measurement):
    """Uniform source ink-box scale; cylindrical warp is the existing mapping."""
    import copy
    line=copy.deepcopy(original);a,b,c,d=measurement['bounds'];scale=25/(d-b)
    x0,y0=350.,1047.;baseline=y0+d*scale;runs=[]
    for row in measurement['rows']:
        if row['bounds'] is None:continue
        ga,gb,gc,gd=row['bounds'];left=x0+(row['cursor']+row['dx']+ga-a)*scale;right=x0+(row['cursor']+row['dx']+gc-a)*scale
        # Font dimensions are normalized to1000 em, as in the historical graph.
        factor=1000/measurement['units_per_em'];sx=float((fa.arc(right)-fa.arc(left))/((gc-ga)*factor));sy=scale*fa.YS/factor
        origin=float(fa.arc(left))-ga*factor*sx
        runs.append({'text':chr(measurement['glyph_aliases'][row['g']]),'font_role':'arabic','x_mm':fa.WIDTH/2+origin,'baseline_z_mm':(fa.BOTTOM-baseline+row['dy']*scale)*fa.YS,'scale_x_mm_per_1000pt_unit':sx,'scale_y_mm_per_1000pt_unit':sy,'source_glyph_bbox_px':[left,baseline-(gd+row['dy'])*scale,right,baseline-(gb+row['dy'])*scale],'shaped_glyph_name':row['g']})
    line.update(runs=runs,tracking_source='Uniform shaped ink-height25px; heaviest Cairo instance within3% width; no independent width fitting',font_instance_weight=measurement['chosen_weight'])
    return line
