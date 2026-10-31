"""Owner-requested masked image runner, using the existing durable paid boundary."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np

from django.conf import settings
from PIL import Image

from . import round_calls as image_guard, spend_reservation
from .round_balm_calls import REPO, OUT, PREFIX, sha, write, append
from .round_balm_sheet import protected_edit, crops_and_drawing, verify

BANNED = ('Banned main motifs: rose flowers, petals, gardens, arches, glow frames, lips, cherries, '
          'botanical line-art wallpaper, the August twelve-rosette, engine-turned cartouche and strapwork moire, '
          'kisses, drips, honey, bees.')
FORMAT = ('Edit only the nine transparent panel windows of image 1: body wrap, cap wrap, round bottom label, '
          'carton back, left side, front, right side, top end, bottom end. One complete lip balm, one idea '
          'across every panel. Printed flat artwork on the exact engine sheet, all panels at the same scale. '
          'The hero stays inside each wrap front-third box; both wrap edges fall on flat ground. '
          'Carton back and bottom copy zones stay flat. Arabic equal or leading. '
          'Crafted artwork for a $1B prestige house; restrained branding; never one colour family everywhere. ')
COPY = ('Provisional lettering across the object: approved "BBROSE" mark from image 2, your own collection name, '
        '"Lip Balm / بلسم شفاه", tint "Rosewater" (three tints: "Rosewater", "Fig Milk", "Ember", '
        'or your own three names), "4.5 g ℮ 0.15 oz". Carton back EN/ES/AR draft: '
        '"Tinted lip balm. Apply to lips. External use only." / '
        '"Bálsamo labial con color. Aplicar en los labios. Solo uso externo." / '
        '"بلسم شفاه ملون. يطبق على الشفاه. للاستعمال الخارجي فقط." '
        '"INCI: owner to supply". Empty ladder-wise truncated EAN-13 FRAME, no bars or digits. '
        'Bottom: empty "Batch / Lote / التشغيلة" field. ')
DONT = ('Do not move or resize panels, paint construction guides or glue/dust/tuck flaps, '
        'add panels, product views, shadows, mockups, scenes, invented INCI, claims or barcode numbers. '
        'No competitor names. Keep the white sheet outside windows unchanged.')


def prompt(seed):
    return FORMAT + '\nSeed: ' + seed + '\n' + COPY + '\n' + BANNED + '\n' + DONT


def edit(key, words, *, parent=None, mask=None, client=None):
    dest=OUT / ('developments/'+key if parent else 'sketches/'+key)
    if (dest/'result.json').exists():
        previous=json.loads((dest/'result.json').read_text())
        expected_target=Path(parent) if parent else OUT/'sheet.png'
        expected_mask=Path(mask) if mask else OUT/'sheet-mask.png'
        if previous['prompt_sha256']!=hashlib.sha256(words.encode()).hexdigest():
            raise ValueError('A resumed image cannot use a different prompt')
        if (REPO/previous['inputs'][0]['path']).resolve()!=expected_target.resolve() or previous['mask']['sha256']!=sha(expected_mask):
            raise ValueError('A resumed image cannot change parent or mask')
        if any(sha(REPO/item['path'])!=item['sha256'] for item in previous['inputs']):
            raise ValueError('A resumed image input changed')
        if not (dest/'crop.json').exists() or not (dest/'drawing.png').exists():crops_and_drawing(dest)
        return previous
    if (dest/'request.json').exists():
        raise ValueError('Prior image attempt unresolved; never silently repurchase '+key)
    logo,logo_sha=image_guard.APPROVED_LOGO
    if sha(logo)!=logo_sha:raise ValueError('Approved logo changed')
    if settings.IMAGE_MODEL!='gpt-image-2':raise ValueError('Requested gpt-image-2 only')
    if image_guard.competitor_in(words):raise ValueError('Competitor in prompt')
    if not verify()['passes']:raise ValueError('Invalid engine sheet')
    target=Path(parent) if parent else OUT/'sheet.png'
    if parent and mask is None:raise ValueError('A development requires an explicit protected-fragment mask')
    mask=Path(mask) if mask else OUT/'sheet-mask.png'
    if parent and not target.resolve().is_relative_to((OUT/'sketches').resolve()):
        raise ValueError('Development parent must be a Round 1 sketch')
    paths=[target,Path(logo)]
    if parent:paths.append(OUT/'sheet.png')
    for path in paths+[mask]:
        if path!=Path(logo) and Image.open(path).size!=(1536,1024):raise ValueError('Wrong dimensions')
    base=np.asarray(Image.open(OUT/'sheet-mask.png').convert('RGBA'))[...,3]
    effective=np.asarray(Image.open(mask).convert('RGBA'))[...,3]
    if np.any((effective==0)&(base!=0)):raise ValueError('Fork mask exposes protected construction')
    if parent and not np.any((base==0)&(effective!=0)):raise ValueError('Fork mask protects no artwork fragment')
    inputs=[{'path':str(p.relative_to(REPO)),'sha256':sha(p)} for p in paths]
    identity={'model':'gpt-image-2','quality':'high','size':'1536x1024','prompt':words,
              'prompt_sha256':hashlib.sha256(words.encode()).hexdigest(), 'inputs':inputs,
              'mask':{'path':str(mask.relative_to(REPO)),'sha256':sha(mask)}}
    dest.mkdir(parents=True,exist_ok=True)
    write(dest/'request.json',identity)
    if client is None:
        from openai import OpenAI
        client=OpenAI(api_key=settings.OPENAI_API_KEY,max_retries=0,timeout=400)
    with ExitStack() as stack:
        files=[stack.enter_context(p.open('rb')) for p in paths]
        mf=stack.enter_context(mask.open('rb'))
        response=spend_reservation.paid_operation(client.images.edit,provider='openai',
            operation=PREFIX+'image/'+key,reservation_prefix=PREFIX,reservation_cap=20,
            count_prefix=PREFIX+'image/',count_cap=26, model='gpt-image-2',quality='high',
            size='1536x1024',image=files,mask=mf,prompt=words,n=1)
    saved=response._rescue_paid_images
    if len(saved)!=1:raise ValueError('Exactly one image required; raw response retained')
    shutil.copyfile(saved[0],dest/'raw.png')
    invariant=protected_edit(target,dest/'raw.png',mask,dest/'picture.png')
    # Alpha windows in the edit target become opaque art; fixed construction stays exact.
    with spend_reservation._connect() as db:
        cost=dict(db.execute('SELECT state,accounted FROM calls WHERE id=?',(response._rescue_reservation_id,)).fetchone())
    rec=dict(identity,reservation_id=response._rescue_reservation_id,
             response_artifact=response._rescue_response_artifact,
             usage=response.model_dump(mode='json').get('usage'),cost_usd=cost['accounted']/1e6,
             billing_state=cost['state'],output_sha256=sha(dest/'picture.png'),invariant=invariant)
    write(dest/'result.json',rec)
    append(OUT/'image-calls.jsonl',dict(rec,key=key))
    crops_and_drawing(dest)
    return rec
