"""Blender4.5 deterministic model: actual12 roots, circular collars, pinned UVs."""
import bpy,sys,json,math,hashlib
from pathlib import Path
from mathutils import Vector
cfg=json.load(open(sys.argv[sys.argv.index('--')+1]));out=Path(cfg['output']);a=cfg['assembly'];spec=cfg['bottle_spec'];diagnostic=cfg.get('diagnostic',False)
for path,digest in [(cfg['bottle_texture'],cfg['bottle_texture_sha256'])]+[(s['texture'],s['texture_sha256']) for s in cfg['surfaces']]:
    if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('Texture changed before scene import.')
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=cfg['samples'];scene.cycles.seed=cfg['seed'];scene.cycles.use_denoising=False
scene.render.resolution_x,scene.render.resolution_y=cfg['resolution'];scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_depth='8';scene.render.film_transparent=False
scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast';scene.view_settings.exposure=0;scene.view_settings.gamma=1
scene.world=bpy.data.worlds.new('studio');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.68,.72,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7

def material(name,colour,rough=.6,metal=0,texture=None):
    m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes;bs=n.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*colour,1);bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metal
    if texture:
        t=n.new('ShaderNodeTexImage');t.image=bpy.data.images.load(texture,check_existing=True);t.interpolation='Linear';m.node_tree.links.new(t.outputs['Color'],bs.inputs['Base Color']);m.node_tree.links.new(t.outputs['Alpha'],bs.inputs['Alpha'])
        if diagnostic:
            e=n.new('ShaderNodeEmission');m.node_tree.links.new(t.outputs['Color'],e.inputs[0]);transparent=n.new('ShaderNodeBsdfTransparent');mix=n.new('ShaderNodeMixShader');m.node_tree.links.new(t.outputs['Alpha'],mix.inputs[0]);m.node_tree.links.new(transparent.outputs[0],mix.inputs[1]);m.node_tree.links.new(e.outputs[0],mix.inputs[2]);m.node_tree.links.new(mix.outputs[0],n.get('Material Output').inputs[0])
    return m
board=material('printed board matte',(.45,.19,.035),.72);edge=material('cardboard edges',(.36,.21,.09),.85);chrome=material('chrome environment approximation',(.72,.77,.82),.18,1)
amber=material('amber fill / clear glass appearance approximation',(.49,.19,.012),.16,.12)
bs=amber.node_tree.nodes.get('Principled BSDF');bs.inputs['Coat Weight'].default_value=.6;bs.inputs['Coat Roughness'].default_value=.08
# Fresnel-driven colour changes communicate glass depth; no physical optics claim.
fres=amber.node_tree.nodes.new('ShaderNodeFresnel');fres.inputs[0].default_value=1.45;ramp=amber.node_tree.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.60,.25,.022,1);ramp.color_ramp.elements[1].color=(.08,.025,.003,1);amber.node_tree.links.new(fres.outputs[0],ramp.inputs[0]);amber.node_tree.links.new(ramp.outputs[0],bs.inputs['Base Color'])
ink=material('bottle r3 additive-equivalent presentation texture',(1,1,1),.5,texture=cfg['bottle_texture'])
surface_mats={s['surface_id']:material(s['surface_id'],(1,1,1),.65,texture=s['texture']) for s in cfg['surfaces']}
parts=[]
def box(name,lo,hi,mat):
    bpy.ops.mesh.primitive_cube_add(size=1,location=tuple((x+y)/2 for x,y in zip(lo,hi)));o=bpy.context.object;o.name=name;o.dimensions=tuple(y-x for x,y in zip(lo,hi));bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat);parts.append(name);return o

def face(name,vertices,mat):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],[(0,1,2,3)]);mesh.update();o=bpy.data.objects.new(name,mesh);scene.collection.objects.link(o);o.data.materials.append(mat);uv=mesh.uv_layers.new(name='surface UV')
    for loop,value in zip(mesh.polygons[0].loop_indices,[(0,0),(1,0),(1,1),(0,1)]):uv.data[loop].uv=value
    return o
box('base',(0,0,0),(180,150,6),edge);box('rear_panel',(0,144,0),(180,150,322),board)
face('header.front',[(0,143.9,222),(180,143.9,222),(180,143.9,322),(0,143.9,322)],surface_mats['header.front'])
for i,seat in enumerate(a['seats']):
    y0=i*a['tread'];y1=(i+1)*a['tread'];z0=0 if i==0 else a['seats'][i-1]
    box('seat-'+str(i),(0,y0,seat-6),(180,y1,seat),edge)
    # Separate circular retention collar6mm above seat: hole diameter31, no square substitutes.
    collar=box('collar-'+str(i),(0,y0,seat),(180,y1,seat+6),board)
    for pos in [p for p in a['positions'] if p['row']==i+1]:
        x,y,z=pos['xyz'];bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=15.5,depth=10,location=(x,y,seat+3));cutter=bpy.context.object;mod=collar.modifiers.new('circular retention opening','BOOLEAN');mod.operation='DIFFERENCE';mod.object=cutter;bpy.context.view_layer.objects.active=collar;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
    box('riser-'+str(i),(0,y0,z0),(180,y0+6,seat),board)
    face('riser.'+str(i+1)+'.front',[(0,y0-.1,z0),(180,y0-.1,z0),(180,y0-.1,seat),(0,y0-.1,seat)],surface_mats['riser.'+str(i+1)+'.front'])
    if i>0:
        for x in [6,87,168]:box('web-'+str(i)+'-'+str(x),(x,y0,6),(x+6,y1,seat-6),edge)
box('front_lip',(0,0,6),(180,6,12),board);face('lip.front',[(0,-.2,6),(180,-.2,6),(180,-.2,12),(0,-.2,12)],surface_mats['lip.front'])
# Full rectangular side support skins carry the unchanged Day4 side proofs.
for side,x in [('left',0),('right',174)]:
    box(side+'-support',(x,0,0),(x+6,150,114),board)
    xx=-.1 if side=='left' else 180.1
    verts=[(xx,150,0),(xx,0,0),(xx,0,114),(xx,150,114)] if side=='left' else[(xx,0,0),(xx,150,0),(xx,150,114),(xx,0,114)]
    face('side.'+side,verts,surface_mats['side.'+side])

def lathe(name,profile,mat,parent):
    vertices=[];faces=[];n=96
    rings=[]
    for e in profile:
        for z,r in [(e['z0'],e['r0']),(e['z1'],e['r1'])]:
            if not rings or rings[-1]!=(z,r):rings.append((z,r))
    for z,r in rings:
        for j in range(n):t=2*math.pi*j/n;vertices.append((r*math.sin(t),-r*math.cos(t),z))
    for i in range(len(rings)-1):
        for j in range(n):faces.append((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j))
    faces.extend([tuple(reversed(range(n))),tuple((len(rings)-1)*n+j for j in range(n))]);mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update();o=bpy.data.objects.new(name,mesh);scene.collection.objects.link(o);o.parent=parent;o.data.materials.append(mat)
    for poly in mesh.polygons:poly.use_smooth=len(poly.vertices)==4
    return o

def wrap(parent):
    w,h=spec['surface']['width_mm'],spec['surface']['height_mm'];nz=96;nt=96;vertices=[];faces=[]
    for iz in range(nz+1):
        z=h*iz/nz;r=14.5
        for e in spec['elevation_proposal']['profile']:
            if e['z0']<=z<=e['z1']:r=e['r0']+(e['r1']-e['r0'])*(z-e['z0'])/(e['z1']-e['z0']);break
        for it in range(nt+1):theta=(-w/2+w*it/nt)/14.5;vertices.append(((r+.035)*math.sin(theta),-(r+.035)*math.cos(theta),z))
    for iz in range(nz):
        for it in range(nt):v=iz*(nt+1)+it;faces.append((v,v+1,v+nt+2,v+nt+1))
    mesh=bpy.data.meshes.new('body.front UV');mesh.from_pydata(vertices,[],faces);mesh.update();o=bpy.data.objects.new(parent.name+'/body.front',mesh);scene.collection.objects.link(o);o.parent=parent;o.data.materials.append(ink);uv=mesh.uv_layers.new(name='authoritative body.front')
    for poly in mesh.polygons:
        poly.use_smooth=True
        for loop in poly.loop_indices:
            vertex=mesh.loops[loop].vertex_index;uv.data[loop].uv=(vertex%(nt+1)/nt,vertex//(nt+1)/nz)

for p in a['positions']:
    root=bpy.data.objects.new('bottle/'+p['id'],None);root['bottle_id']=p['id'];root.location=p['xyz'];scene.collection.objects.link(root)
    lathe(root.name+'/glass-fill',spec['elevation_proposal']['profile'][:2],amber,root);lathe(root.name+'/collar',spec['elevation_proposal']['profile'][2:3],chrome,root);lathe(root.name+'/cap',spec['elevation_proposal']['profile'][3:],chrome,root);wrap(root)
    # Front spray aperture is a declared presentation detail, not a mechanism.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=1.25,location=(0,0,0));nozzle=bpy.context.object;nozzle.name=root.name+'/spray aperture';nozzle.parent=root;nozzle.location=(0,-10.48,103.2);nozzle.scale=(1,.1,1);nozzle.data.materials.append(material(nozzle.name,(.015,.015,.015),.4))
roots=[{'id':o['bottle_id'],'xyz':list(o.location),'hidden':o.hide_render} for o in scene.objects if 'bottle_id' in o]
if len(roots)!=12 or len({r['id'] for r in roots})!=12:raise ValueError('Scene bottle count invalid')
box('studio floor',(-1000,-1000,-7),(1000,1000,-6),material('warm grey studio',(.73,.72,.69),.9))
# Actual50mm scale bar on y=-20 front reference plane, not a universal perspective ruler.
box('50mm bar',(20,-20,-4),(70,-18,-2),material('scale bar',(.05,.05,.05),.9))
for name,location,energy,size in [('key',(-300,-350,650),120000,400),('strip',(420,-50,500),100000,300),('top',(90,400,650),160000,350)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.shape='RECTANGLE';data.size=size;data.size_y=size*2;o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);o.location=location;o.rotation_euler=(Vector((90,60,150))-o.location).to_track_quat('-Z','Y').to_euler()
locations={'front':(90,-500,550),'median':(90,-650,650),'three-quarter':(440,-570,570),'plan-front':(90,-390,850)};cameras={}
for name,loc in locations.items():
    target=Vector((90,65,161));data=bpy.data.cameras.new(name);data.type='PERSP';data.sensor_fit='VERTICAL';data.sensor_height=32;distance=(Vector(loc)-target).length;data.lens=32*distance/391;data.clip_start=1;data.clip_end=5000;o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);o.location=loc;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();cameras[name]=o
if diagnostic:
    # Camera-only emission for EVERY material. No reflective/indirect pathway
    # can transport an edited copy line outside its actual mapped surface.
    scene.cycles.samples=1;scene.cycles.max_bounces=0;scene.cycles.transparent_max_bounces=8
    for m in bpy.data.materials:
        if not m.use_nodes:continue
        n=m.node_tree.nodes;bs=n.get('Principled BSDF')
        if bs is None:continue
        colour=bs.inputs['Base Color'];alpha=bs.inputs['Alpha'];em=n.new('ShaderNodeEmission');em.inputs[0].default_value=colour.default_value
        if colour.is_linked:m.node_tree.links.new(colour.links[0].from_socket,em.inputs[0])
        if alpha.is_linked:
            trans=n.new('ShaderNodeBsdfTransparent');mix=n.new('ShaderNodeMixShader');m.node_tree.links.new(alpha.links[0].from_socket,mix.inputs[0]);m.node_tree.links.new(trans.outputs[0],mix.inputs[1]);m.node_tree.links.new(em.outputs[0],mix.inputs[2]);m.node_tree.links.new(mix.outputs[0],n.get('Material Output').inputs[0])
        else:m.node_tree.links.new(em.outputs[0],n.get('Material Output').inputs[0])
from bpy_extras.object_utils import world_to_camera_view
bpy.context.view_layer.update()
def pixel(point):
    q=world_to_camera_view(scene,cameras['front'],Vector(point));return [q.x*cfg['resolution'][0],(1-q.y)*cfg['resolution'][1]]
regions={}
for o in scene.objects:
    if o.type=='MESH' and (o.name=='header.front' or o.name.endswith('/body.front')):
        points=[pixel(o.matrix_world@v.co) for v in o.data.vertices];regions[o.name]=[min(q[0] for q in points)-2,min(q[1] for q in points)-2,max(q[0] for q in points)+2,max(q[1] for q in points)+2]
sample_points=[]
for theta,z,colour in [(-.5,50,'red'),(.5,50,'green'),(-.5,20,'blue'),(.5,20,'yellow')]:
    sample_points.append({'expected':colour,'pixel':pixel((68.9+14.535*math.sin(theta),22.333333-14.535*math.cos(theta),6+z))})
manifest={'blender_version':bpy.app.version_string,'bottle_roots':roots,'parts':parts,'diagnostic_regions':regions,'uv_samples':sample_points,'camera':{name:{'eye_mm':list(o.location),'aim_mm':[90,65,161],'projection':'perspective','lens_mm':o.data.lens,'sensor_height_mm':32,'reference_plane_vertical_field_mm':391} for name,o in cameras.items()},'scale_bar':{'length_mm':50,'y_plane_mm':-20,'note':'Perspective scale only on this reference plane; companion orthographic drawing gives1:1 dimensions.'},'label':cfg['label'],'assembly_sha256':cfg['assembly_sha256'],'bottle_spec_hash':cfg['bottle_spec_hash'],'bottle_texture_sha256':cfg['bottle_texture_sha256'],'surfaces':cfg['surfaces'],'collar_detail':'31mm circular holes; collar lower face at seat,6mm thickness; provisional construction'}
(out/'scene-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'display.blend'))
for view in cfg['views']:
    scene.camera=cameras[view];scene.render.filepath=str(out/(view+'.png'));bpy.ops.render.render(write_still=True)
