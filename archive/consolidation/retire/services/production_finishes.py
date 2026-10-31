"""The finishes a production file actually specifies — read from the file, never from its picture (Day 8 §2a).

A house production design (.ai saved PDF-compatible, or .pdf) names its finishes three ways: as a spot ink (a
Separation or DeviceN colourant such as "烫金", "Gold Foil", "UV", "Varnish"), as a layer (an optional-content group
named "UV", "击凸"), or in its own words on the artboard ("局部UV", "hot stamping"). Each is read here and mapped to one
finish word by a closed vocabulary, Chinese and English, with the evidence kept: which channel, which page, the exact
name or words. A finish the vocabulary does not know is never guessed; a file PyMuPDF cannot open is said, not skipped,
and so is a channel of an opened file it cannot read (an object, the native data, the layers), and a file MuPDF had to
repair to read it (what the repair lost is dropped without a word).
"""
from __future__ import annotations

import re
from pathlib import Path

#: finish word → the names and words that say it (lower-case English; Chinese as written). Order matters only for
#: reporting; one name may say two finishes ("烫金击凸" = foil + emboss).
FINISHES = {
    'hot foil gold': ('烫金', 'gold foil', 'hot foil gold', 'foil gold', 'gold stamping', 'hot stamping gold', '金箔', '电化铝金'),
    'hot foil silver': ('烫银', 'silver foil', 'foil silver', 'silver stamping'),
    'hot foil (colour unnamed)': ('hot foil', 'hot stamp', 'hot-stamp', 'foil stamping', 'foiling', '烫印', '电化铝', 'foil'),
    'holographic / laser': ('镭射', 'laser foil', 'holographic', 'holo foil', '幻彩', '全息'),
    'rose-gold foil': ('烫玫瑰金', 'rose gold foil', 'rose-gold foil', '玫瑰金'),
    'spot UV': ('局部uv', 'spot uv', 'spot-uv', 'uv', '局部光油', 'spot varnish'),
    'reverse UV': ('逆向uv', '逆向', 'reverse uv'),
    'varnish': ('varnish', '光油', '上光', '过油'),
    'emboss': ('击凸', '凸', 'emboss', 'embossed', 'embossing', '压凸'),
    'deboss': ('压凹', '凹', 'deboss', 'debossed', 'debossing', '压纹'),
    'matte lamination': ('哑膜', '覆哑膜', 'matte lamination', 'matt lamination', 'matte film'),
    'gloss lamination': ('光膜', '覆光膜', 'gloss lamination', 'glossy lamination'),
    'soft-touch': ('触感膜', '肤感膜', 'soft touch', 'soft-touch', 'velvet lamination'),
    'window': ('开窗', 'window', '窗口', 'pvc window', '透明窗'),
    'flocking': ('植绒', 'flocking', 'flocked'),
    'pearlescent': ('珠光', 'pearlescent', 'pearl paper', '珠光纸'),
    'screen print': ('丝印', 'silk screen', 'screen print', 'silkscreen'),
    'white ink': ('印白', '白墨', 'white ink', 'opaque white'),
    'die line': ('刀线', '刀模', 'die line', 'dieline', 'die-cut', 'cutting line', 'cut line'),
}
#: names that are inks, not finishes (process and Pantone inks are recorded as inks, never as a finish)
_INK = re.compile(r'^(?:pantone|pms)\b|^(?:cyan|magenta|yellow|black|all|none)$', re.I)
_WORDS_LIMIT = 4000          # characters of a page's words read for finish words


def _finishes_in(text: str) -> list:
    said = text.lower()
    found = []
    for finish, names in FINISHES.items():
        for name in names:
            if re.fullmatch(r'[a-z\- ]+', name):
                hit = re.search(r'(?<![a-z0-9])%s(?![a-z0-9])' % re.escape(name), said)
            else:
                hit = name in said
            if hit:
                found.append(finish)
                break
    # a named colour of foil makes the unnamed one redundant
    if 'hot foil (colour unnamed)' in found and any(f.startswith('hot foil ') and f != 'hot foil (colour unnamed)' for f in found):
        found.remove('hot foil (colour unnamed)')
    return found


def _object(doc, xref: int):
    """Object ``xref``'s source as PyMuPDF reads it, or None when it cannot (a damaged object, a corrupt object stream)
    — counted by ``_colourants`` into the record's ``objects_unreadable``, never read as an object that names nothing."""
    try:
        return doc.xref_object(xref, compressed=False)
    except Exception:  # noqa: BLE001 — returned as None and counted by the caller: said, never skipped
        return None


def _colourants(doc) -> tuple:
    """Every Separation / DeviceN colourant name the file's pages use, read from the PDF objects, and how many objects
    PyMuPDF could not read (their colourants unknown, never none)."""
    # fix (gate review, Day 8): a damaged object was skipped ("a damaged object names nothing; the census says the file
    # opened"), so a file whose ink objects could not be read said OPENED with no colourant and nothing said why; each
    # object that cannot be read is now counted, and the record and the census say so
    names, unreadable = set(), 0
    for xref in range(1, doc.xref_length()):
        obj = _object(doc, xref)
        if obj is None:
            unreadable += 1
            continue
        for match in re.finditer(r'/Separation\s*/([^\s/\[\]<>()]+)', obj):
            names.add(_unescape(match.group(1)))
        for match in re.finditer(r'/DeviceN\s*\[([^\]]*)\]', obj):
            for part in re.findall(r'/([^\s/\[\]<>()]+)', match.group(1)):
                names.add(_unescape(part))
    return sorted(names), unreadable


def _unescape(name: str) -> str:
    """A PDF name's #xx escapes decoded (UTF-8 where it decodes, else latin-1)."""
    raw = re.sub(rb'#([0-9A-Fa-f]{2})', lambda m: bytes([int(m.group(1), 16)]), name.encode('latin-1', 'replace'))
    for codec in ('utf-8', 'gb18030', 'latin-1'):
        try:
            return raw.decode(codec)
        except UnicodeDecodeError:
            continue
    return name


#: the state of a file's native-data channel, as ``native_strings`` reads it
NATIVE_DATA = ('absent', 'read', 'undecodable', 'incomplete')
#: what Illustrator's native data begins with when it is stored plain (measured on Day 8: the decompressed native data
#: and the AIMetaData stream of all 91 house files begin "%!PS-Adobe-3.0")
_PLAIN_NATIVE = b'%!PS-Adobe-'


def _stream(doc, xref: int) -> tuple:
    """Object ``xref``'s stream as PyMuPDF decodes it, with what MuPDF said while it decoded it: ``(data, said)``.
    ``data`` is None when the object is no stream, or when PyMuPDF raises (a reference out of range, a damaged object):
    a part not read, either way. ``said`` is MuPDF's warnings and errors during this read alone, '' when it said
    nothing; a part it spoke about is not the part as written (measured on PyMuPDF 1.28 / MuPDF 1.29: a Flate part
    damaged early decodes to b'' after "zlib error: …" and "read error; treating as end of file", one damaged late to
    garbled bytes of about its length after "ignoring zlib error: incorrect data check" alone, and a part a truncated
    file cut short to its first bytes after "PDF stream Length incorrect")."""
    import fitz
    # Day 8 residual: this said "b'' when its data would not inflate" — measured false: a Flate part damaged late
    # decodes, without raising, to garbled non-empty bytes, MuPDF only warning, and native_strings read them as names
    # ('read'). MuPDF's warnings are now read around the read: flushed and emptied before it — flushed first, as MuPDF
    # folds a warning repeated back to back into a count it says only at a flush, so a count an earlier read owes is set
    # aside and a warning this read repeats is said again — and read after it. Any word counts, not a list of decode
    # messages (the library has dozens: zlib, lzw, a85d, faxd, brotli, aes, a stream's length): none of the 10,050
    # native-data part reads in the 91 house files says one (measured 2026-10-20), so the normal path is unchanged
    fitz.TOOLS.mupdf_warnings()
    try:
        data = doc.xref_stream(xref)
    except Exception:  # noqa: BLE001 — returned as None: the native data is then 'incomplete', never read whole
        return None, fitz.TOOLS.mupdf_warnings()
    return data, fitz.TOOLS.mupdf_warnings()


def _inflate(blob: bytes):
    """``blob`` inflated by zlib, or None when it will not decompress (the native data is then 'undecodable')."""
    import zlib
    try:
        return zlib.decompress(blob)
    except zlib.error:
        return None


def _utf8(raw: bytes):
    """``raw`` decoded as UTF-8, or None when it is not UTF-8: encoded data, never a name (the UTF-8 filter the gate
    review of Day 8 judged legitimate, moved here unchanged in what it keeps and drops)."""
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return None


def native_strings(doc) -> tuple:
    """The strings of an Illustrator file's own native data (AIPrivateData, ZStandard- or zlib-compressed, or plain
    under its PostScript header): layer, swatch, brush and live-text names, decoded UTF-8 — with the state of that
    channel, one of ``NATIVE_DATA``: 'absent' (no object PyMuPDF can read names it, in a file MuPDF did not repair),
    'read', 'undecodable' (its compressed data will not decompress, or it names neither a compression marker this reader
    knows nor the plain header, or MuPDF warned while it decoded a part that still returned bytes — garbled or cut
    short: its bytes are never read as text) or 'incomplete' (a part it names could not be read, or the parts it names
    are not 1..NumBlock, or no object names it in a file MuPDF repaired — absence there cannot be told from loss). The
    strings are [] when nothing was decoded."""
    import subprocess
    # fix (gate review, Day 8): a damaged object was skipped ("a damaged object holds no private data"), a part that
    # could not be read was joined as b'' (``or b''``) and data that would not decompress read as b'', so a file whose
    # native data failed said OPENED and declared nothing; the channel's state is now returned with the strings (a
    # damaged object is counted once, by _colourants). A part not read (None, b'', an error) or a number missing from
    # 1..NumBlock (Illustrator writes the parts' count; measured equal and contiguous in all 91 house files) makes it
    # 'incomplete'; a decompression that fails on whole data makes it 'undecodable'. The strings are what they were.
    priv = None
    for xref in range(1, doc.xref_length()):
        obj = _object(doc, xref)
        if obj is not None and '/AIPrivateData1' in obj:     # an object that cannot be read is counted by _colourants
            priv = obj
            break
    if priv is None:
        # Day 8 residual: a file MuPDF repaired (it rebuilt the cross-reference table from what it found) drops the
        # objects it lost without raising, so a private dict a truncation took read 'absent' and the census read the
        # file clean (measured: LP-2018.ai and YB-1030(LG5862)..ai cut to 10 % of their bytes open repaired, with no
        # private dict); absence in a repaired file cannot be told from loss. Read after the scan above: MuPDF also
        # repairs lazily, the first time an object is not where the table says
        return [], ('incomplete' if doc.is_repaired else 'absent')
    refs = dict(re.findall(r'/AIPrivateData(\d+)\s+(\d+)\s+0\s+R', priv))
    reads = [_stream(doc, int(refs[k])) for k in sorted(refs, key=int)]
    parts = [part for part, _said in reads]
    numbers = sorted(int(k) for k in refs)
    blocks = re.search(r'/NumBlock\s+(\d+)', priv)
    expected = int(blocks.group(1)) if blocks else len(numbers)
    complete = bool(parts) and all(parts) and numbers == list(range(1, expected + 1))
    data = b''.join(part for part in parts if part)
    # Day 8 residual: a part MuPDF warned about while decoding it that still returned bytes is garbled or cut short
    # (measured: one Flate part damaged late read 'read', with 345 to 401 strings scanned from its garbled bytes); no
    # string is read from the data then — 'undecodable', or 'incomplete' with a part missing. A part that returned
    # nothing is a part not read, as before
    garbled = any(part and said for part, said in reads)
    if garbled:
        native = None
    elif b'%AI24_ZStandard_Data' in data:
        blob = data[data.find(b'%AI24_ZStandard_Data') + len(b'%AI24_ZStandard_Data'):]
        run = subprocess.run(['zstd', '-d', '-c'], input=blob, capture_output=True)
        native = run.stdout if run.returncode == 0 else None
    elif b'%AI12_CompressedData' in data:
        native = _inflate(data[data.find(b'%AI12_CompressedData') + len(b'%AI12_CompressedData'):])
    elif data.startswith(_PLAIN_NATIVE):
        native = data
    else:
        # fix (gate review, Day 8, second pass): data that named no marker this reader knows was read as plain text
        # ("else: native = data") and said 'read', so a marker damaged on disk read its undecoded bytes as names (a copy
        # of LP-2018.ai with one marker byte changed: 30 noise strings where 1014 were, and a clean census); plain data
        # is now recognised by its own header, _PLAIN_NATIVE, and data that names neither is not decoded — no string is
        # read from it (the one case where the strings are not what they were): 'undecodable', or 'incomplete' with a
        # part missing
        native = None
    if native is None:
        return [], ('undecodable' if complete else 'incomplete')
    found = set()
    for raw in re.findall(rb'\(((?:[^()\\\r\n]|\\.){1,120})\)', native):
        text = _utf8(raw)
        if text is not None and looks_like_a_name(text):
            found.add(text)
    return sorted(found), ('read' if complete else 'incomplete')


def looks_like_a_name(text: str) -> bool:
    """A native string that reads as a name — a layer, a swatch, a style, a live word — and not encoded data that
    happens to sit in parentheses (measured on Day 8: ASCII85 runs such as ``^UV0j`` read as "spot UV" in 91 files):
    printable, no control characters, at most 60 characters, and at least 70 % letters, spaces or CJK."""
    if not text or len(text) > 60 or any(ord(ch) < 32 for ch in text):
        return False
    wordy = sum(1 for ch in text if ch.isalpha() or ch == ' ' or '\u4e00' <= ch <= '\u9fff')
    return wordy / len(text) >= 0.7


def _ocgs(doc) -> tuple:
    """The file's optional-content groups as PyMuPDF reads them, with None; or {} with the exception's name when it
    cannot read them (the layers then unknown, never none). A file without optional content reads as {} and None
    (measured on PyMuPDF 1.28: get_ocgs() returns {} for it, and does not raise)."""
    # fix (gate review, Day 8, second pass): the ``or {}`` after get_ocgs() stood in for nothing — PyMuPDF 1.28 returns
    # its own dict on every path (read in its source) — so it is gone, and a None from another version fails loudly
    try:
        return doc.get_ocgs(), None
    except Exception as exc:  # noqa: BLE001 — said, never skipped: the record's layers_error names it
        return {}, type(exc).__name__


def finishes_of(path) -> dict:
    """The finishes one production file specifies, with the evidence for each: ``{state, finishes{word: [evidence]},
    colourants, layers, inks, native_strings, objects_unreadable, native_data, layers_error, repaired}``; state OPENED
    or UNREADABLE (with why). An OPENED file says which channels could not be read: the count of objects PyMuPDF could
    not read, its native data as one of ``NATIVE_DATA``, the layers' read error by its exception's name (or None), and
    whether MuPDF had to repair the file, on open or while it was read (objects it lost dropped without a word: what
    they declare unknown, never none); an UNREADABLE file read none of them, and holds None in all four."""
    import fitz
    path = Path(path)
    try:
        doc = fitz.open(str(path))
    except Exception as exc:  # noqa: BLE001 — said, never skipped
        return {'state': 'UNREADABLE', 'why': '%s: %s' % (type(exc).__name__, str(exc)[:160]), 'finishes': {},
                'colourants': [], 'layers': [], 'inks': [],
                'objects_unreadable': None, 'native_data': None, 'layers_error': None, 'repaired': None}
    evidence = {}
    colourants, objects_unreadable = _colourants(doc)
    inks = [c for c in colourants if _INK.search(c)]
    for name in colourants:
        if _INK.search(name):
            continue
        for finish in _finishes_in(name):
            evidence.setdefault(finish, []).append({'channel': 'spot colourant', 'name': name})
    # fix (gate review, Day 8): an error reading the layers was read as no layers ("a file without optional content has
    # no layers to name" — such a file reads as {} and never raised); the error is now named in layers_error
    ocgs, layers_error = _ocgs(doc)
    layers = [str(v.get('name') or '') for v in ocgs.values()]
    for name in layers:
        for finish in _finishes_in(name):
            evidence.setdefault(finish, []).append({'channel': 'layer', 'name': name})
    native, native_data = native_strings(doc)
    for name in native:
        if _INK.search(name) or name.startswith('AI_'):      # inks and Illustrator's own default library names
            continue
        for finish in _finishes_in(name):
            evidence.setdefault(finish, []).append({'channel': 'native name', 'name': name[:80]})
    for number, page in enumerate(doc):
        words = page.get_text('text')[:_WORDS_LIMIT]
        for finish in _finishes_in(words):
            line = next((ln.strip() for ln in words.splitlines() if _finishes_in(ln)), '')
            evidence.setdefault(finish, []).append({'channel': 'words', 'page': number + 1, 'words': line[:120]})
        if number >= 3:
            break
    # Day 8 residual: a file MuPDF had to repair drops what it lost without raising — references to lost objects read
    # as "declares nothing", every count stayed 0 (_colourants counts only objects that raise) and the census read the
    # file clean (measured: LP-2018.ai and YB-1030(LG5862)..ai cut to 10, 50 or 90 % of their bytes, 'repaired' each
    # time); it is now said. Read here, after every channel was read, never at open alone: MuPDF also repairs lazily,
    # the first time an object is not where the cross-reference table says (measured: a table entry moved 3 bytes
    # opens unrepaired and is repaired by the first read of that object). Whenever the repair came, the record's native
    # data is never 'absent' in a repaired file
    repaired = doc.is_repaired
    doc.close()
    if repaired and native_data == 'absent':
        native_data = 'incomplete'
    return {'state': 'OPENED', 'finishes': evidence, 'colourants': colourants, 'layers': layers, 'inks': inks,
            'native_strings': len(native), 'objects_unreadable': objects_unreadable, 'native_data': native_data,
            'layers_error': layers_error, 'repaired': repaired}


SEEN_PROMPT = (
    "This is a page of a cosmetics brand's own production artwork file (packaging: flat artwork, unfolded box templates, "
    "mockups, specification callouts). List ONLY finishes that this page shows or names: (1) callout labels or notes that "
    "name a finish — quote the exact text as printed, Chinese or English (e.g. 烫金, 烫银, 局部UV, 击凸, 压凹, 镭射, 开窗, "
    "hot foil, spot UV, emboss, deboss, window, matte lamination, soft touch); (2) finishes visibly rendered on a mockup "
    "(metallic foil sheen, raised emboss, a window). Never infer a finish from colour alone: flat gold-coloured ink is "
    "not foil unless it is labelled or rendered with a metallic sheen. Answer as JSON.")
SEEN_SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {
    'callouts': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'properties': {
        'text': {'type': 'string'}, 'finish': {'type': 'string'}}, 'required': ['text', 'finish']}},
    'rendered': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'properties': {
        'finish': {'type': 'string'}, 'where': {'type': 'string'}}, 'required': ['finish', 'where']}},
    'product': {'type': 'string', 'description': 'what product this artwork is for, in a few words'}},
    'required': ['callouts', 'rendered', 'product']}


def finishes_seen(preview_png, *, model, operation, reservation_prefix=None, reservation_cap=None) -> dict:
    """A vision model's reading of the finishes a production file's preview shows or names — a model's reading, kept as
    such (channel "seen (model)"), mapped to the same finish words; the file's own declarations above outrank it."""
    import base64
    import json

    import anthropic
    from django.conf import settings

    from apps.pipeline.services.day6_critic import critic_image_bytes
    from apps.pipeline.services.spend_reservation import paid_operation
    data, _ = critic_image_bytes(preview_png)
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=0, timeout=120)
    response = paid_operation(client.messages.create, provider='anthropic', operation=operation, model=model,
                              reservation_prefix=reservation_prefix, reservation_cap=reservation_cap, max_tokens=800,
                              output_config={'format': {'type': 'json_schema', 'schema': SEEN_SCHEMA}},
                              messages=[{'role': 'user', 'content': [
                                  {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                                                               'data': base64.b64encode(data).decode()}},
                                  {'type': 'text', 'text': SEEN_PROMPT}]}])
    text = ''.join(b.text for b in response.content if getattr(b, 'type', '') == 'text')
    try:
        read = json.loads(text)
    except ValueError:
        return {'state': 'UNREAD', 'why': 'the answer was not JSON', 'finishes': {}}
    evidence = {}
    for row in read.get('callouts') or []:
        for finish in _finishes_in(row.get('text', '') + ' ' + row.get('finish', '')):
            evidence.setdefault(finish, []).append({'channel': 'callout seen (model)', 'words': row.get('text', '')[:80]})
    for row in read.get('rendered') or []:
        for finish in _finishes_in(row.get('finish', '')):
            evidence.setdefault(finish, []).append({'channel': 'rendered (model)', 'where': row.get('where', '')[:80]})
    return {'state': 'READ', 'finishes': evidence, 'product': read.get('product', ''), 'raw': read,
            'reservation_id': getattr(response, '_rescue_reservation_id', None)}


def _a_channel_unread(record: dict) -> bool:
    """An OPENED file one of whose channels could not be read — an object PyMuPDF could not read, native data
    'undecodable' or 'incomplete', an error reading the layers, or a file MuPDF had to repair (what it lost is dropped
    without a word): what that channel declares is unknown, never none."""
    # Day 8 residual: a repaired file read clean here (its lost objects raised nothing, its counts stayed 0); it is one
    return (record['objects_unreadable'] > 0 or record['native_data'] in ('undecodable', 'incomplete')
            or record['layers_error'] is not None or record['repaired'])


def census(paths) -> dict:
    """``finishes_of`` over many files: per file, and per finish how many files carry it (die lines counted apart); the
    files that did not open ('unreadable'), and the opened files one of whose channels could not be read, counted
    ('opened_with_an_unreadable_channel') and named ('paths_with_an_unreadable_channel') — never credited a finish; the
    files MuPDF had to repair are among them, and counted ('opened_repaired') and named ('paths_repaired') apart too."""
    per_file, counts = {}, {}
    for path in paths:
        record = finishes_of(path)
        per_file[str(path)] = record
        for finish in record['finishes']:
            counts[finish] = counts.get(finish, 0) + 1
    # fix (gate review, Day 8): an opened file whose objects, native data or layers could not be read was counted as
    # read, its silence there taken for "declares nothing"; such files are now counted and named apart. No finish is
    # added for them: files_by_finish counts only what a record's finishes name.
    unread = sorted(p for p, r in per_file.items() if r['state'] == 'OPENED' and _a_channel_unread(r))
    # Day 8 residual: the repaired files are named apart as well, so the census says why they are among the unread
    repaired = sorted(p for p, r in per_file.items() if r['state'] == 'OPENED' and r['repaired'])
    return {'files': len(per_file), 'unreadable': sum(1 for r in per_file.values() if r['state'] != 'OPENED'),
            'opened_with_an_unreadable_channel': len(unread), 'paths_with_an_unreadable_channel': unread,
            'opened_repaired': len(repaired), 'paths_repaired': repaired,
            'files_by_finish': dict(sorted(counts.items(), key=lambda kv: -kv[1])), 'per_file': per_file}
