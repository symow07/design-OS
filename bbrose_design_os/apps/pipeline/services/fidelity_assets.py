"""Reference-pixel extraction and declared cylindrical mapping; no image provider."""
from pathlib import Path
import hashlib
import json
import math
import cv2
import numpy as np
from PIL import Image

APP = Path(__file__).resolve().parents[3]
ROOT = APP.parent
MEASUREMENT = ROOT / 'docs/audit/day-4/concept-147-measurement.json'
INSTRUMENT = ROOT / 'docs/audit/day-4/fidelity-instrument.json'
CONCEPT = APP / 'docs/design_presets/s2422-sun-repair-v1/concept-reference.png'
RADIUS = 14.5
BODY_TOP = 547
BOTTOM = 1470
XS = 29 / 372
YS = 108 / 1375
WIDTH = math.pi * RADIUS
HEIGHT = (BOTTOM - BODY_TOP) * YS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def arc(x):
    return RADIUS * np.arcsin(np.clip((np.asarray(x) - 505) / 186, -1, 1))


def ssim(a, b, mask):
    """Declared 11px Gaussian local luminance SSIM; evaluated on artwork support."""
    a = cv2.cvtColor(np.asarray(a, dtype=np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float64)
    b = cv2.cvtColor(np.asarray(b, dtype=np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float64)
    blur = lambda v: cv2.GaussianBlur(v, (11, 11), 1.5)
    ma, mb = blur(a), blur(b)
    va, vb = blur(a*a)-ma*ma, blur(b*b)-mb*mb
    cov = blur(a*b)-ma*mb
    score = ((2*ma*mb+6.5025)*(2*cov+58.5225))/((ma*ma+mb*mb+6.5025)*(va+vb+58.5225))
    if not np.any(mask):
        raise ValueError('The fidelity mask must contain actual reference artwork.')
    return float(score[mask > 0].mean())


def project(rgba, *, source_shape=(1536, 1024)):
    """Project an actual exported flat master to fixed reference-image coordinates."""
    h, w = source_shape
    factor = 2
    xx, yy = np.meshgrid((np.arange(w*factor,dtype=np.float32)+.5)/factor-.5,
                         (np.arange(h*factor,dtype=np.float32)+.5)/factor-.5)
    mx = ((arc(xx) + WIDTH/2) / WIDTH * (rgba.shape[1]-1)).astype(np.float32)
    my = ((yy-BODY_TOP) * YS / HEIGHT * (rgba.shape[0]-1)).astype(np.float32)
    premultiplied=np.asarray(rgba,dtype=np.float32).copy()
    premultiplied[:,:,:3] *= premultiplied[:,:,3:4]/255
    result = cv2.remap(premultiplied, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
    result[(xx < 319) | (xx > 691) | (yy < BODY_TOP) | (yy > BOTTOM)] = 0
    result=cv2.resize(result,(w,h),interpolation=cv2.INTER_AREA)
    result[:,:,:3]=np.where(result[:,:,3:4]>0,result[:,:,:3]*255/np.maximum(result[:,:,3:4],.001),0)
    return np.clip(np.round(result),0,255).astype(np.uint8)


def composite(bg, layer):
    alpha = layer[:, :, 3:4].astype(float) / 255
    return np.clip(np.round(layer[:, :, :3]*alpha + bg[:, :, :3]*(1-alpha)), 0, 255).astype(np.uint8)


def extract(destination):
    """Retain source RGB; derive an explicit matte and interpolate without invention."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    measurement = json.loads(MEASUREMENT.read_text())
    assert sha(CONCEPT) == measurement['source']['sha256']
    image = np.asarray(Image.open(CONCEPT).convert('RGB'))
    # This polygon selects the spatial ROI only; it never becomes artwork or a vector trace.
    roi = np.zeros(image.shape[:2], np.uint8)
    # Row envelope excludes the vertical glass reflection; it is not a printed motif.
    envelope = np.array([(578,684,691),(600,658,686),(650,603,638),(700,565,593),
                         (750,540,566),(800,531,569),(850,545,591),(900,588,636),
                         (950,632,668),(1000,655,686),(1050,661,689),(1100,647,682),
                         (1150,614,691),(1200,550,691),(1250,490,691),(1300,475,691),
                         (1350,484,675),(1380,529,600)],float)
    for y in range(576,1382):
        left,right = np.interp(y,envelope[:,0],envelope[:,1]),np.interp(y,envelope[:,0],envelope[:,2])
        roi[y,max(0,int(left)-5):min(692,int(right)+6)] = 255
    f = image.astype(float)
    # Amber is red/yellow; the cream stroke raises blue. Keep faint upper-edge pixels.
    evidence = np.minimum((f[:,:,2] - .24*f[:,:,1] - 8)/24, (f[:,:,1]-75)/28)
    alpha = np.clip(evidence, 0, 1) * (roi/255)
    alpha[image[:,:,0] < 120] = 0
    # Keep the full source extent; source colour is retained even under soft edge alpha.
    source = np.dstack([image, np.round(alpha*255).astype(np.uint8)])
    Image.fromarray(source).save(destination/'swoosh-source-matte.png')
    support = (alpha > .05).astype(np.uint8)*255
    Image.fromarray(support).save(destination/'swoosh-reference-support.png')
    # Remove ALL ink from the reference-derived material field before new artwork overlays it.
    all_ink = support.copy()
    for element in measurement['elements']:
        if element['id'] == 'swoosh':
            continue
        x0,y0,x1,y1 = element['bbox_px']
        patch = image[y0-3:y1+3,x0-3:x1+3]
        light = ((patch[:,:,0]>170)&(patch[:,:,1]>150)&(patch[:,:,2]>120)).astype(np.uint8)*255
        all_ink[y0-3:y1+3,x0-3:x1+3] |= light
    all_ink = cv2.dilate(all_ink, np.ones((5,5),np.uint8))
    material = cv2.inpaint(image, all_ink, 15, cv2.INPAINT_TELEA)
    Image.fromarray(material).save(destination/'material-field.png')
    Image.fromarray(all_ink).save(destination/'removed-ink-mask.png')
    # 1000ppi destination is explicitly interpolated, not a claim of new source detail.
    outw,outh = math.ceil(WIDTH/25.4*1000), math.ceil(HEIGHT/25.4*1000)
    sx = np.linspace(-WIDTH/2, WIDTH/2, outw)
    sy = np.linspace(BODY_TOP, BOTTOM, outh)
    mx,my = np.meshgrid(505 + 186*np.sin(sx/RADIUS), sy)
    flat = cv2.remap(source, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
    Image.fromarray(flat).save(destination/'swoosh-flat.png')
    returned = project(flat)
    ref = composite(material, source)
    recovered = composite(material, returned)
    metric_mask = cv2.dilate(support, np.ones((7,7),np.uint8))
    fidelity = ssim(ref, recovered, metric_mask)
    if fidelity < .90:
        raise ValueError('The interpolated swoosh did not reproduce its source at source resolution.')
    report = {'tool':'OpenCV INTER_CUBIC inverse-cylinder resampling; local CPU, no generative model',
              'cost_usd':0,'interpolated':True,'native_source_ppi_vertical':25.4/YS,
              'effective_output_ppi':[outw/WIDTH*25.4,outh/HEIGHT*25.4],
              'source_resolution_roundtrip_ssim':fidelity,'threshold':.90,
              'mask_sha256':sha(destination/'swoosh-reference-support.png'),
              'source_rgba_sha256':sha(destination/'swoosh-source-matte.png'),
              'flat_rgba_sha256':sha(destination/'swoosh-flat.png'),
              'alpha_limitation':'Single-image matte is an estimate; source RGB retained. No curve tracing, redrawing or cropping.',
              'material_limitation':'Reference-derived 2D colour/light field after ink removal; not physical optics.'}
    (destination/'extraction.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
