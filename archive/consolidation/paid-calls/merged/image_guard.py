"""The guard every image call passes BEFORE payment (D-D8-2, D-D8-7, D-D8-10; re-rooted for Day 9, D-D9-1), and the call log §8 asserts from.

Refused, by name, before a byte is sent:
- an input whose bytes are a design the system made to date (D-D8-2: every concept, drawing, lid, surface, mockup and
  paid picture) — by sha256 against a denylist hashed from where those live, however the file was renamed or copied;
- an input that is a web or competitor picture (D-D8-7: research only) — anything under the web quarantine, by path
  and by sha256;
- an input from outside the roots a Day 8 call may draw on (our engine's renders, the approved mark, house-design
  crops made for a named trait with the client's name masked, the house library's materials and previews);
- a prompt that names a competitor brand (D-D8-7);
- a provider other than OpenAI or a model other than ``settings.IMAGE_MODEL`` (D-D8-10).
Every call — allowed or refused — is one line of ``docs/audit/day-9/image-calls.jsonl`` (Day 8's log is closed): the operation, the provider
and model, each input's role, path and sha256, the prompt's sha256 and words, the quality and size, and the outcome.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings

ROOT = Path(settings.BASE_DIR)                      # bbrose_design_os/
REPO = ROOT.parent
# [Day 9] each day's calls are its own log; Day 8's log (docs/audit/day-8/image-calls.jsonl) is closed and kept
# [Day 10] and Day 9's (docs/audit/day-9/image-calls.jsonl) is closed and kept
# [Day 11] and Day 10's (docs/audit/day-10/image-calls.jsonl) is closed and kept
# [Day 12] and Day 11's (docs/audit/day-11/image-calls.jsonl) is closed and kept
CALL_LOG = REPO / 'docs' / 'audit' / 'day-12' / 'image-calls.jsonl'
DENYLIST_CACHE = ROOT / 'var' / 'day8' / 'image-guard-denylist.json'
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.tif', '.tiff', '.bmp'}

#: D-D8-2 — where the designs the system made to date live (each image file hashed into the denylist)
REJECTED_ROOTS = (
    ROOT / 'media' / 'generated', ROOT / 'media' / 'concepts', ROOT / 'media' / 'concept_thumbs',
    ROOT / 'media' / 'drawing_views', ROOT / 'media' / 'rejected', ROOT / 'media' / 'palette',
    ROOT / 'media' / 'containers', ROOT / 'media' / 'container_handoff', ROOT / 'media' / 'task_refs',
    ROOT / 'var' / 'rescue_spend' / 'responses', ROOT / 'docs' / 'roadmap' / 'palt_m7',
    ROOT / 'apps' / 'pipeline' / 'tests' / 'fixtures_124',
    REPO / 'docs' / 'audit' / 'day-4', REPO / 'docs' / 'audit' / 'day-5', REPO / 'docs' / 'audit' / 'day-6',
    REPO / 'docs' / 'audit' / 'day-7', REPO / 'docs' / 'audit' / 'codex-2026-10-18',
    # [Day 9, D-D9-1] Day 8's directions are closed and its builds are rejected designs (UNCHANGED: "no rejected design
    # (Day 8's builds included) ... ever goes to an image model"): every picture under Day 8's audit folder
    REPO / 'docs' / 'audit' / 'day-8',
    # [Day 10, D-D10-4] "never a web picture or a rejected design": every Day 9 picture but the owner's pick (APPROVED_PICK)
    REPO / 'docs' / 'audit' / 'day-9',
)
#: D-D8-7 — web and competitor pictures: research only, never an input
WEB_ROOTS = (ROOT / 'media' / 'web_quarantine',)
#: the roots a Day 11 image call may draw on (the owner's picks by their path and sha256: APPROVED_PICKS); Day 10's work
#: (Golden Hour, test one) is not among them — no Golden Hour picture reaches a Ẓilāl call (D-D11 §8)
#: [Day 12] the roots moved on to Day 12's own work: its style reference is the lid master re-traced by D-D12-9's reader
#: (docs/audit/day-12/zilal/lid), its sheets drawn there; Day 11's files are not today's (as Day 10's were not)
ALLOWED_ROOTS = (
    REPO / 'docs' / 'audit' / 'day-12',                      # [Day 12] today's own work
    REPO / 'materials',                                       # the house library (D-D7-1) — material, texture, layer
    ROOT / 'var' / 'design_intelligence' / 'previews' / 'materials',   # its Day 7 previews, by hash
    REPO / 'var' / 'design_intelligence' / 'previews' / 'materials',
)
#: [Day 9 §3] "Inputs: the approved logo only (no engine renders)": the approval's own source raster, one exact file, its
#: bytes pinned — allowed by path AND sha256 (docs/brand/mark/approval.json, source_png)
APPROVED_LOGO = (ROOT / 'media' / 'brand' / 'bbrose-logo.png', 'e107a0989d9cedf52980166cca0d368cdb4f1059ed8aff0c51badac7cee58c18')
#: [Day 10, D-D10-4] "every image call carries the pick as its style reference": the owner's pick, one exact file, its bytes
#: pinned — allowed by path AND sha256 (CURRENT_DECISIONS.md, Day 10), though it sits under Day 9's rejected root
APPROVED_PICK = (REPO / 'docs' / 'audit' / 'day-9' / 'sketches' / 'A-2.3' / 'lid.png',
                 '4293fe8b20a8c39e9776e433267fd6b36bfa89ca72f4381710f32a639f797de8')
#: [Day 11, D-D11-1] the pick changes to Ẓilāl: the sketch B-1.3, one exact file, its bytes pinned (CURRENT_DECISIONS.md,
#: Day 11); Golden Hour's pick stays approved for its own five fixes (D-D11-5: its new tray picture)
APPROVED_ZILAL = (REPO / 'docs' / 'audit' / 'day-9' / 'sketches' / 'B-1.3' / 'lid.png',
                  '090a543ce1b2ead1b4904fb555961ec8baa6848bc6e725438f3a77801584198d')
APPROVED_PICKS = (APPROVED_PICK, APPROVED_ZILAL)
#: D-D8-7 — the house's own production designs: an input only as a crop of a named trait, the client's name masked
HOUSE_DESIGN_ROOTS = (REPO / 'materials' / 'house-designs', REPO / 'docs' / 'brand' / 'house_references' / 'files')
#: D-D8-7 — no competitor brand name in an image prompt (the board's brand sites, the palette leaders, the prestige
#: houses the market board studied, and the Middle-East houses); matched as whole words, any case
COMPETITORS = (
    'Rare Beauty', 'Fenty', 'Glossier', 'Rhode', 'Huda Beauty', 'Huda', 'Charlotte Tilbury', 'Summer Fridays', 'Kayali',
    'Merit', 'Tower 28', 'ILIA', 'Byredo', 'Laneige', 'Saie', 'Haus Labs', 'Pat McGrath', 'Natasha Denona', 'Dior',
    'YSL', 'Yves Saint Laurent', 'Makeup by Mario', 'Chanel', 'Hermès', 'Hermes', 'Guerlain', 'Givenchy', 'Gucci',
    'Tom Ford', 'Victoria Beckham', 'Hourglass', 'Westman', 'Sisley', 'Rose Inc', 'Lancôme', 'Lancome', 'Estée Lauder',
    'Estee Lauder', 'MAC Cosmetics', 'NARS', 'Urban Decay', 'Anastasia Beverly Hills', 'Too Faced', 'Benefit',
    'Clinique', 'Bobbi Brown', 'Armani', 'Valentino', 'Prada', 'Burberry', 'Louboutin', 'Sephora', 'Asteri', 'Mikyajy',
    'Shiffa', 'Kylie', 'Morphe', 'ColourPop', 'Kiko', 'Bourjois', 'Maybelline', "L'Oréal", "L'Oreal", 'Revlon',
)


class ImageCallRefused(Exception):
    """An image call refused before payment — the reason in words."""


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


#: a sha256 as ``_sha`` writes it — 64 lowercase hex digits, the only form the denylist is keyed by
_SHA256 = re.compile(r'[0-9a-f]{64}')


def _digest(value):
    """``value`` when it is a sha256 as ``_sha`` writes it, else None — a record that carries no digest has none (the
    gate review of Day 8: a missing or malformed sha256 is never read as a clean one)."""
    return value if isinstance(value, str) and _SHA256.fullmatch(value) else None


#: D-D8-2 rejects every design made BEFORE Day 8; a paid picture bought under a Day 8 operation (a sketch, a build's
#: plate) is today's own work, filed by the ledger under its reservation id — never a rejected design, or the chosen
#: sketch could not be its own build's style reference (§5 Stage 2)
TODAY_OPERATION_PREFIX = 'day12/'     # [Day 11] Day 10's paid pictures are no longer today's own work (D-D11 §8);
                                      # [Day 12] nor Day 11's


def _todays_responses(responses_root: Path) -> set:
    """The reservation ids (response folder names) the ledger files under a Day 8 operation."""
    import sqlite3
    ledger = responses_root.parent / 'ledger.sqlite3'
    if not ledger.exists():
        return set()
    with sqlite3.connect(str(ledger), timeout=30) as db:
        rows = db.execute("select id from calls where operation like ?", (TODAY_OPERATION_PREFIX + '%',)).fetchall()
    return {r[0] for r in rows}


def _images_under(roots) -> list:
    out = []
    for root in roots:
        if root.exists():
            found = [p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
            if root.name == 'responses' and root.parent.name == 'rescue_spend':
                today = _todays_responses(root)
                found = [p for p in found if p.relative_to(root).parts[0] not in today]
            out += found
    return out


def _cached_sha(entry, st):
    """The sha256 the cache holds for a file hashed at its present size and mtime_ns — else None, and it is hashed
    again."""
    # Day 8 residual, documented and not closed: a path whose size and mtime_ns are both unchanged is trusted without
    # reading it. A rewrite of the same size whose mtime is put back (touch -r, or os.utime with ns=) keeps the stale
    # sha256 here, and a copy of its new bytes passes check() until denylist(refresh=True) hashes every file again or
    # the file's size or mtime moves. Measured on this APFS volume (2026-10-20): such a rewrite, and a file of the same
    # size and mtime renamed over the path, keep st_size and st_mtime_ns; st_ctime_ns moves (the kernel sets it on a
    # write and on the utime call itself, and touch and os.utime cannot set it back) and the rename changes st_ino.
    # Keying on those two would catch both cases measured here; that is left for a ruling, since a new key hashes every
    # file once. Hashing every file on every call is not done: check() builds the denylist on every guarded image call,
    # and audit() on every audit, over 326,193 paths and 11.7 GB under the rejected and web roots (counted from the
    # cache, 2026-10-20), so every byte would be read again on each call.
    if isinstance(entry, dict) and entry.get('size') == st.st_size and entry.get('mtime_ns') == st.st_mtime_ns:
        return _digest(entry.get('sha256'))
    return None


def denylist(*, refresh: bool = False) -> dict:
    """``{"rejected": {sha: path}, "web": {sha: path}}`` — every image under the rejected and the web roots, hashed and
    cached (``var/day8/image-guard-denylist.json``) with the size and mtime_ns each file was hashed at; a file the cache
    has not seen, or one whose size or mtime has changed since, is hashed again."""
    files = {'rejected': _images_under(REJECTED_ROOTS), 'web': _images_under(WEB_ROOTS)}
    cache = {}
    if DENYLIST_CACHE.exists() and not refresh:
        try:
            cache = json.loads(DENYLIST_CACHE.read_text())
        except ValueError:
            cache = {}
    # fix (gate review, Day 8): the cache held {sha: path} and was read back by path alone, so a file in a rejected root
    # rewritten in place kept its first sha256 and a copy of its new bytes passed check(). Each path is now cached with
    # the size and mtime_ns it was hashed at (its stat read before its bytes) and hashed again when either differs. A
    # cache in the old format has no 'by_path' table, so every file in it is hashed again, none of its shas trusted
    # (and a process still running the old code finds no 'rejected' or 'web' table here, so it hashes, never fails).
    hashed = cache['by_path'] if 'by_path' in cache else {}
    out, by_path = {}, {}
    for kind, paths in files.items():
        known = hashed[kind] if kind in hashed else {}                  # path -> {sha256, size, mtime_ns}
        table, entries = {}, {}
        for p in paths:
            st = p.stat()
            sha = _cached_sha(known.get(str(p)), st)
            if sha is None:
                sha = _sha(p)
            entries[str(p)] = {'sha256': sha, 'size': st.st_size, 'mtime_ns': st.st_mtime_ns}
            table[sha] = str(p)
        out[kind], by_path[kind] = table, entries
    DENYLIST_CACHE.parent.mkdir(parents=True, exist_ok=True)
    DENYLIST_CACHE.write_text(json.dumps({'by_path': by_path}))
    return out


def _under(path: Path, roots) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def competitor_in(prompt: str) -> str:
    """The first competitor brand the prompt names, or ''."""
    for name in COMPETITORS:
        if re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(name), prompt, re.I):
            return name
    return ''


def check(inputs, prompt: str, *, provider: str = 'openai', model: str | None = None, deny: dict | None = None) -> list:
    """The inputs as they would be sent, each ``{role, path, sha256}`` — or ``ImageCallRefused`` with the reason."""
    if provider != 'openai':
        raise ImageCallRefused('D-D8-10: generated images come from OpenAI only — provider %r refused' % provider)
    if (model or settings.IMAGE_MODEL) != settings.IMAGE_MODEL:
        raise ImageCallRefused('D-D8-10: the image model is %s — %r refused' % (settings.IMAGE_MODEL, model))
    name = competitor_in(prompt)
    if name:
        raise ImageCallRefused('D-D8-7: the prompt names a competitor brand (%s)' % name)
    deny = deny if deny is not None else denylist()
    checked = []
    for item in inputs:
        role, path = item['role'], Path(item['path'])
        if not path.exists():
            raise ImageCallRefused('input %s (%s) does not exist' % (path, role))
        sha = _sha(path)
        approved_logo = any(path.resolve() == pinned.resolve() and sha == pinned_sha
                            for pinned, pinned_sha in (APPROVED_LOGO,) + APPROVED_PICKS)
        # [Day 9] the approved logo is the house's own mark, never a design the system made: archived audit folders
        # (the Codex snapshot) hold byte-identical copies of it, so it is matched by its exact path AND sha before the
        # rejected-design hash check — its copies anywhere else stay refused
        if sha in deny['rejected'] and not approved_logo:
            raise ImageCallRefused('D-D8-2: input %s (%s) is a design the system made to date (%s)'
                                   % (path.name, role, deny['rejected'][sha]))
        if sha in deny['web'] or _under(path, WEB_ROOTS):
            raise ImageCallRefused('D-D8-7: input %s (%s) is a web picture — research only' % (path.name, role))
        if not approved_logo and not _under(path, ALLOWED_ROOTS):
            raise ImageCallRefused('input %s (%s) is outside the roots a Day 11 image call may draw on' % (path, role))
        if _under(path, HOUSE_DESIGN_ROOTS) and role != 'house trait crop':
            raise ImageCallRefused('D-D8-7: a house design reaches an image call only as a crop of a named trait')
        checked.append({'role': role, 'path': str(path), 'sha256': sha})
    return checked


def log_call(record: dict) -> None:
    """One line of the call log (append-only)."""
    CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = dict(record, at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat())
    with open(CALL_LOG, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')


def guarded_call(invoke, *, operation: str, inputs, prompt: str, quality: str, size: str, **extra):
    """``invoke(checked_inputs)`` after ``check`` passes; the call logged either way; a refusal raised before payment."""
    try:
        checked = check(inputs, prompt)
    except ImageCallRefused as exc:
        # Day 8 residual: the caller's extra fields come FIRST, so none of them (an 'outcome', a 'model', 'inputs')
        # can overwrite what the guard itself records about the call
        log_call({**extra, 'operation': operation, 'provider': 'openai', 'model': settings.IMAGE_MODEL, 'outcome': 'refused',
                  'why': str(exc), 'inputs': [{'role': i['role'], 'path': str(i['path'])} for i in inputs],
                  'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'prompt': prompt,
                  'quality': quality, 'size': size})
        raise
    try:
        result = invoke(checked)
    except Exception as exc:
        log_call({**extra, 'operation': operation, 'provider': 'openai', 'model': settings.IMAGE_MODEL, 'outcome': 'failed',
                  'why': '%s: %s' % (type(exc).__name__, str(exc)[:300]), 'inputs': checked,
                  'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'prompt': prompt,
                  'quality': quality, 'size': size})
        raise
    log_call({**extra, 'operation': operation, 'provider': 'openai', 'model': settings.IMAGE_MODEL, 'outcome': 'made',
              'inputs': checked, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'prompt': prompt,
              'quality': quality, 'size': size,
              **({'result': result} if isinstance(result, dict) else {})})
    return result


#: the outcomes ``guarded_call`` writes, read exactly as written: sent ('made', 'failed') or refused before payment
def _is_approved_logo(item: dict) -> bool:
    """An input row naming the approval's own source raster (APPROVED_LOGO) or one of the owner's picks (APPROVED_PICKS: Day
    10's and Day 11's): its path is the file's and its sha256 the recorded one."""
    path = item['path'] if 'path' in item else None
    if not isinstance(path, str) or 'sha256' not in item:
        return False
    return any(Path(path).resolve() == pinned.resolve() and item['sha256'] == sha
               for pinned, sha in (APPROVED_LOGO,) + APPROVED_PICKS)


OUTCOMES = ('made', 'failed', 'refused')


def audit(log_path: Path = CALL_LOG) -> dict:
    """§8 — asserted from the call log: no Gemini, Pacdora or Blender call; no rejected design and no web picture in any
    image call; no competitor name in any image prompt. A sent call whose row does not record what it sent (no inputs,
    an input with no sha256, no prompt) cannot be asserted clean: it is counted, and the audit does not hold. Nor does
    it hold on a row whose outcome is none of ``OUTCOMES`` ('unknown_outcome'), on a log that does not exist
    ('log_present' False, every count None) or on a log with no rows ('log_empty')."""
    # Day 8 residual (the gate review's follow-up): a missing log was read as no rows and audited holds=True with
    # calls=0, though nothing was read and so nothing was asserted. It does not hold now, says log_present False, and
    # every count is None: unknown, never 0 (as a cost whose token counts are missing is unknown, never $0).
    present = log_path.exists()
    # Day 8 residual: rows are split on '\n' only — str.splitlines() also splits on U+2028 / U+0085, which a prompt
    # written with ensure_ascii=False may carry inside its JSON string
    rows = [json.loads(l) for l in log_path.read_text(encoding='utf-8').split('\n') if l.strip()] if present else []
    deny = denylist()
    made = [r for r in rows if r.get('outcome') in ('made', 'failed')]
    # Day 8 residual: only 'made' and 'failed' rows were read and 'refused' counted, so a row with no outcome, or with
    # one that is not exactly one of the three (another case, a typo), was checked by nothing and the audit still held.
    # It is counted by name and the audit does not hold. It stays out of 'sent' and out of the input and prompt counts,
    # which read only what is known to have been sent, so calls = sent + refused + unknown_outcome.
    unknown_outcome = [r for r in rows if r.get('outcome') not in OUTCOMES]
    bad_provider = [r for r in rows if r.get('provider') != 'openai'
                    or (r.get('outcome') != 'refused' and re.search(r'gemini|pacdora|blender', str(r.get('model')), re.I))]
    # fix (gate review, Day 8): the inputs and the prompt were read with [] and '' as their defaults, so a sent row with
    # no inputs or no prompt read as clean, while a missing provider counted as bad; such a row, or one with an input
    # carrying no sha256, is now counted by name (a row once) and the audit does not hold. A refused row sent nothing
    # and is not read here.
    sent_shas = [(r, [_digest(i.get('sha256')) if isinstance(i, dict) else None for i in r['inputs']])
                 for r in made if isinstance(r.get('inputs'), list)]
    no_input_sha = [r for r in made if not isinstance(r.get('inputs'), list)] + [r for r, shas in sent_shas if None in shas]
    # Day 9: the approved logo is exempt here exactly as check() exempts it — by its path and its sha256 together (a copy of
    # the same bytes under a rejected root is a rejected design; the approval's own source raster is not)
    bad_inputs = [r for r in made if isinstance(r.get('inputs'), list) for i in r['inputs']
                  if isinstance(i, dict) and (_digest(i.get('sha256')) in deny['rejected'] or _digest(i.get('sha256')) in deny['web'])
                  and not _is_approved_logo(i)]
    no_prompt = [r for r in made if not isinstance(r.get('prompt'), str)]
    bad_prompts = [r for r in made if isinstance(r.get('prompt'), str) and competitor_in(r['prompt'])]
    counts = {'calls': len(rows), 'sent': len(made), 'refused': len([r for r in rows if r.get('outcome') == 'refused']),
              'non_openai_or_named_tool': len(bad_provider), 'rejected_or_web_inputs': len(bad_inputs),
              'competitor_prompts': len(bad_prompts), 'sent_without_input_sha256': len(no_input_sha),
              'sent_without_prompt': len(no_prompt), 'unknown_outcome': len(unknown_outcome)}
    if not present:
        counts = {key: None for key in counts}                       # no log was read: no count was measured
    # Day 8 residual: a log with no rows does not hold either. guarded_call writes one row for every call it is given
    # (made, failed or refused), and every paid Day 8 picture went through it: the log's 22 rows (18 sketches, 4 build
    # plates) are, operation for operation, the spend ledger's 22 OpenAI image calls of Day 8 (checked 2026-10-20). So
    # a Day 8 log with no rows cannot tell "no image call was made" from "its rows were lost, cut or never written", and
    # zero rows assert nothing about the calls §8 asks about. It is reported (log_empty, its counts measured as 0). A
    # log of refusals alone still holds, because it records every call.
    return dict(counts, log_present=present, log_empty=(not rows) if present else None,
                holds=(present and len(rows) > 0 and not unknown_outcome and not bad_provider and not bad_inputs
                       and not bad_prompts and not no_input_sha and not no_prompt))
