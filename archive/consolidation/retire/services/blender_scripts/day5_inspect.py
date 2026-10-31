"""Read-only census of the actual saved Blender scene, not expected roots alone."""
import bpy,json,sys
from pathlib import Path
out=Path(sys.argv[sys.argv.index('--')+1]);rows=[]
for o in bpy.context.scene.objects:
    if 'bottle_id' not in o:continue
    children=[]
    for c in o.children:
        if c.type!='MESH':continue
        hidden=c.hide_render or o.hide_render or any(x.hide_render for x in c.users_collection)
        children.append({'component':c.name.split('/')[-1],'hidden':hidden,'vertices':len(c.data.vertices),'faces':len(c.data.polygons)})
    rows.append({'id':o['bottle_id'],'xyz':list(o.location),'hidden':o.hide_render,'children':children})
out.write_text(json.dumps({'blender_version':bpy.app.version_string,'bottle_roots':rows},indent=2)+'\n')
