"""Owner-pinned Day5 concept inputs; geometry is derived, never generated."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from . import fidelity_assets as fa,fidelity_master as fm
from .display_concepts import reference
ROOT=fa.ROOT/'docs/audit/day-5'
COMMON='''Create one assembled BBROSE Sun Repair countertop display concept, centred straight-on with no yaw, clean neutral studio ground. Exact structure from geometry image: exactly TWELVE identical bottles, THREE STEPPED ROWS OF FOUR,180 W x150 D x322 H mm, rises54mm, seats6/60/114mm,100mm header and front lip. Show all12 positions distinctly. The bottle is unchanged:29mm diameter,108mm overall provisional height, clear glass, amber fill, chrome cap and the supplied Sun Repair artwork. Header copy: BBROSE, SUN REPAIR, SERUM, سيروم صن ريبير, Revive + Smooth. Brand/name/descriptor hierarchy; name readable at2m, contrast and quiet space. Concept text may be approximate. House references supply style principles only: ignore their containers, copy, stars, dots and sunburst. No roses, arches, wallpaper, extra products,8or16 bottles, floor display,booth,people or props. Graphics belong on stand surfaces; never bridge empty space or change the product. Show the complete object and all bottle bases, with margin.'''
DIRECTIONS=[
 {'id':'D1','name':'Amber Current','story':'A single cream gesture flows through an amber lacquer field. The dark ground makes the bottle glow and the name lead.','palette_roles':{'dominant':'amber to deep brown','secondary':'deep brown','accent':'cream'},'type_system':'large centred contrast serif name; condensed supporting copy','focal_point':'large centred SUN REPAIR above one continuous swoosh','quiet_zones':'around title and behind bottle identities','material_finish':'matte-laminated printed cardboard; selective spot gloss on swoosh','header_profile':'rectangle180x100','why_distinctive':'A full-height continuous gesture links header and risers.','layout':'centred','type_scale_pairing':'large serif + condensed','image_language':'continuous gesture','pattern_coverage':'one linked field','colour_hierarchy':'amber dominant','silhouette':'rectangular','prompt':'Matte-laminated printed cardboard. Amber-to-deep-brown gradient connects header and risers as one field. One generous cream swoosh continues across printable faces with selective spot gloss; dominant full-height gesture, never corner decoration. Large centred SUN REPAIR on rectangular header, cream support copy, generous quiet space. Deep brown contrast behind amber bottles. Restrained lacquer highlights; not acrylic.'},
 {'id':'D2','name':'Amber Light','story':'Translucent amber decks catch the light in front of a dark printed back. A clear left-aligned title balances a luminous gesture.','palette_roles':{'dominant':'warm dark brown back','secondary':'transparent amber','accent':'cream and bright edges'},'type_system':'left-aligned large condensed sans name; modest serif accent','focal_point':'glowing bottles and asymmetric title','quiet_zones':'dark field behind products','material_finish':'translucent amber acrylic decks and lip; opaque printed back','header_profile':'rectangle180x100','why_distinctive':'Transparency and illuminated edges replace the printed gradient.','layout':'asymmetric left title','type_scale_pairing':'large condensed sans','image_language':'edge light and isolated swoosh','pattern_coverage':'back only, transparent decks','colour_hierarchy':'dark dominant','silhouette':'rectangular','prompt':'Translucent amber acrylic decks and lip, visible6mm thickness and light-catching edges, with opaque warm-dark-brown printed back. Rectangular header; left-aligned cream SUN REPAIR, crisp descriptor, brand above. One luminous cream swoosh occupies opposing side; quiet field behind bottles. Same positions, heights and envelope. No opaque gradient printed over every transparent acrylic surface.'},
 {'id':'D3','name':'Quiet S','story':'Warm white gives the amber product room to breathe. A broad shaped header carries a single amber sweep and compact type.','palette_roles':{'dominant':'warm white','secondary':'deep amber type','accent':'amber swoosh'},'type_system':'compact serif name with spaced condensed support','focal_point':'broad S upper silhouette','quiet_zones':'most of header and risers','material_finish':'matte printed cardboard','header_profile':'connected broad S upper perimeter inside180x100','why_distinctive':'An inverted palette and shaped perimeter give the family its quietest expression.','layout':'compact offset title','type_scale_pairing':'compact serif + spaced condensed','image_language':'shaped contour and single flat sweep','pattern_coverage':'sparse header only','colour_hierarchy':'warm white dominant','silhouette':'broad S header','prompt':'Warm-white printed cardboard with deep amber typography and one amber swoosh. Shape ONLY the100mm-high header upper perimeter into a broad buildable2D swoosh contour within180x100mm envelope. Connected panel with ample copy space; no freestanding ribbon, spiral or unsupported extension. Compact carefully spaced title, abundant white space, quietest direction. Decks, bottle positions and envelope unchanged.'}]


def prepare(destination=None):
    p=Path(destination) if destination is not None else ROOT/'concept-inputs';p.mkdir(exist_ok=False)
    assembly=fa.ROOT/'docs/audit/day-4/stand-family/assembly-spec.json'
    spec=json.loads((ROOT/'master/design-spec.json').read_text())
    # True front elevation from canonical positions; each of the12 silhouettes is separately drawn.
    k=4;im=Image.new('RGB',(1000,1450),'white');d=ImageDraw.Draw(im);ox,oy=140,1360
    xy=lambda x,z:(ox+x*k,oy-z*k)
    rect=lambda x0,z0,x1,z1,fill=None:d.rectangle([xy(x0,z1),xy(x1,z0)],fill=fill,outline='#52616b',width=2)
    rect(0,0,180,322,'#f4f4f1');rect(0,222,180,322,'#fffaf0')
    for row,seat in reversed(list(enumerate([6,60,114]))):
        for col,x in enumerate([26.7,68.9,111.1,153.3]):
            pts=[]
            for profile in spec['elevation_proposal']['profile']:
                pts.extend([xy(x-profile['r0'],seat+profile['z0']),xy(x-profile['r1'],seat+profile['z1'])])
            for profile in reversed(spec['elevation_proposal']['profile']):pts.extend([xy(x+profile['r1'],seat+profile['z1']),xy(x+profile['r0'],seat+profile['z0'])])
            d.polygon(pts,fill='#fffdf7',outline='#273e50',width=2)
            d.text(xy(x-5,seat+45),f'{row+1}.{col+1}',fill='#273e50')
    for z in [0,6,60,114]:d.line([xy(0,z),xy(180,z)],fill='#52616b',width=2)
    d.text((20,10),'EXACT GEOMETRY - FRONT ELEVATION - 12 BOTTLES / 3 x 4',fill='black')
    d.text((20,35),'180 W x 150 D x 322 H mm; rise54; seats6/60/114; header100',fill='black')
    im.save(p/'geometry-front.png')
    refs=[reference(ROOT/'master/projected-master.png','product, exact','bottle-r3-'+fm.digest(spec)),reference(p/'geometry-front.png','geometry, exact','family322-'+fa.sha(assembly))]
    crops={'069':[5940,190,7790,1140],'043':[4961,847,5826,1599],'048':[450,1420,1650,2600]}
    provenance=[]
    for number,box in crops.items():
        source=fa.ROOT/f'docs/brand/house_references/previews-day5/{number}-page-1.png';out=p/f'house-{number}.png'
        Image.open(source).crop(box).save(out);refs.append(reference(out,'house, style','house-'+number));provenance.append({'id':number,'source':str(source.relative_to(fa.ROOT)),'source_sha256':fa.sha(source),'crop_xyxy':box,'crop_sha256':fa.sha(out)})
    axes=['layout','type_scale_pairing','material_finish','image_language','pattern_coverage','colour_hierarchy','silhouette']
    checks=[{'a':a['id'],'b':b['id'],'different_axes':[key for key in axes if a[key]!=b[key]]} for i,a in enumerate(DIRECTIONS) for b in DIRECTIONS[i+1:]]
    assert all(len(x['different_axes'])>=3 for x in checks)
    record={'bottle_revision':3,'bottle_spec_hash':fm.digest(spec),'bottle_review_state':spec['review_state'],'assembly_sha256':fa.sha(assembly),'geometry_authority':'derived front elevation from pinned positions and elevation profile; provisional structure','references':refs,'house_crops':provenance,'directions':DIRECTIONS,'distinctness':checks,'common_prompt':COMMON,'trend_brief_sha256':fa.sha(ROOT/'trend-brief.md')}
    (p/'directions.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n');return record
