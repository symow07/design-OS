"""§BH42(b)+(c) — CAPTIONS for the ruled scope, with the spend bounded and declared.

SCOPE, resolved from records rather than re-derived: the 254 design files listed in
docs/design_intelligence/sittings/bh38/design_pdfs.json (226 .ai + 28 .pdf, the §BH28
extraction's extent as the register states it at OWNER_BLOCKER_CLEARANCE.md:19894) and
the PRODUCTION rows of the tier record. Re-deriving the 254 from the inventory instead
returns 258 and sweeps in a licence agreement that is not a design — which is why the
list is read from the record that defines it.

WHAT A CAPTION IS. Derived and machine-written. It describes what is visible and is
EVIDENCE OF NOTHING ABOUT RIGHTS: the tier beside every row is the tier record's, and a
row that is not PRODUCTION carries a placement refusal. A REFERENCE asset's caption may
be read; its bytes may never be placed (§BH37/§BH39).

THE PALETTE IS MEASURED, NOT ASKED FOR. A hex a model names is a guess; a hex counted
from the rendered pixels is a reading. The clustering follows §BH38's idiom for this same
corpus: ΔE76 ≤ 8 in Lab, ranked by share of the frame.

THE SPEND IS BOUNDED AND DECLARED (§BH42(c)). A sample is captioned first, the total is
projected from it, and a projection over the cap REFUSES: the run does not begin. The
default cap is the §AE cap of fifty dollars. The token counts come from the API's own
usage; the two rates are the only assumption and are recorded in the output.

The renders land under var/brain/ (git-ignored, derived). The RECORD is tracked under
docs/design_intelligence/captions/ by §BH43(a), so the dollar is paid once: a resumed run
reads it and pays only for the contents it does not already hold. materials/ is read-only
and is only ever read.

    bbrose_design_os/tools/brain/caption_scope.py --sample 10          # measure and project, caption nothing else
    bbrose_design_os/tools/brain/caption_scope.py --run                # caption the scope, refusing over the cap
"""
import argparse
import base64
import json
import math
import os
import pathlib
import re
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sources as S

OUTER = S.OUTER
DESIGN_LIST = OUTER / "docs" / "design_intelligence" / "sittings" / "bh38" / "design_pdfs.json"
ENV = OUTER / "bbrose_design_os" / ".env"
RENDERS = S.BRAIN_DIR / "renders"
PALETTES = S.BRAIN_DIR / "palettes.json"   # derived, ignored: sha -> measured palette
CAPTIONS = S.BRAIN_DIR / "captions.json"    # the pre-§BH43 shape, still READ by --record for a migration

# §BH43(a) — THE CAPTION RECORD IS TRACKED. The record leaves the git-ignored var/ and
# becomes tracked evidence: a JSONL keyed by content sha256, one line per content with
# every path that carries it, beside an index carrying the run header. It is MACHINE-WRITTEN
# and it is evidence of NOTHING about rights — the tier record beside each row owns that.
# The model export, the vectors and the SQLite index stay derived and ignored; only this
# record, which cost dollars to make, is kept. A resumed run reads it and pays only for
# what it does not already hold, so the dollar is paid once.
TRACKED_DIR = OUTER / "docs" / "design_intelligence" / "captions"
TRACKED_JSONL = TRACKED_DIR / "captions.jsonl"
TRACKED_INDEX = TRACKED_DIR / "INDEX.json"
TRACKED_RECORD_TYPE = "brain_captions/1.1"
TRACKED_UNCAPTIONABLE = TRACKED_DIR / "uncaptionable.jsonl"

# §BH43(b) — the REFERENCE library joins the scope. The arm is BUILT and OFF, and the reason
# is worth stating plainly: §BH42(e) rules that an image in scope with no caption and no named
# reason is UNCAPTIONED and the commit is REFUSED. Turning this on before the REFERENCE
# captions exist would therefore make the tree un-gateable — correctly, because the scope
# really would not be covered. The first REFERENCE run reached 50 of 2,716 images and then
# died on "credit balance is too low"; until that balance is restored there is no buying the
# captions, so the switch stays off and says so. Turn it on for the run that buys them:
#     CAPTION_SCOPE_REFERENCE=1 bbrose_design_os/tools/brain/caption_scope.py --run --resume --cap 15
# and it becomes the default in the commit that lands those captions.
REFERENCE_IN_SCOPE = os.environ.get("CAPTION_SCOPE_REFERENCE", "0") != "0"

# Formats no local renderer opens. Named with a reason and NOT read: attempting to render an
# archive or a font buys nothing and costs gigabytes of I/O. Anything plausibly an image —
# .ai .psd .eps .svg and every raster format — IS attempted, and a failure there is recorded
# with the renderer's own message.
NOT_IMAGE_SUFFIXES = {".zip", ".rar", ".7z", ".tar", ".gz", ".ttf", ".otf", ".ttc", ".woff",
                      ".woff2", ".txt", ".js", ".css", ".html", ".htm", ".json", ".xml",
                      ".ovpn", ".ase", ".csv", ".md", ".doc", ".docx", ".xls", ".xlsx"}
# Moving pictures. Their bytes could yield a frame, but this renderer draws still images and
# no frame grabber is wired, so they are named for what they are rather than left to fail with
# a raster decoder's confusing message.
MOVING_SUFFIXES = {".mov", ".mp4", ".avi", ".mkv", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv"}

MODEL = "claude-haiku-4-5-20251001"
RATE_IN, RATE_OUT = 1.00, 5.00        # dollars per million tokens, published for MODEL
DEFAULT_CAP_USD = 50.0                # the §AE cap, as §BH42(c) names it
LONG_EDGE = 1400
PALETTE_SAMPLE = 160
PALETTE_DELTA = 8.0

PROMPT = """You are cataloguing a design asset for a private design archive. Describe ONLY what is visible.

Return STRICT JSON with these keys and nothing else:
  "subject":      what the image shows, one sentence.
  "product_form": the physical product or format if one is depicted (bottle, jar, tube, carton, sachet, label, poster, pattern, icon set, mockup, photograph, …), else null.
  "technique":    the production or illustration technique visible (flat vector, gradient mesh, 3D render, photograph, hand-drawn, halftone, line art, collage, …), else null.
  "finish":       any surface finish visible (matte, gloss, foil, metallic, embossed, transparent, holographic, …), else null.
  "layout":       how the frame is organised, one sentence (grid, centred, stacked, radial, full-bleed, repeating tile, …).
  "text_seen":    a list of legible words or short phrases in the image; [] if none.
  "language":     the script of that text (latin, arabic, mixed, none).

Say null where a field is not visible. Do not guess at brands, ownership, licensing or provenance."""

RIGHTS_NOTE = ("DERIVED and machine-written: evidence of nothing about rights. The tier beside this row is "
               "the tier record's, never this caption's; anything but PRODUCTION may not be placed.")


def srgb_to_lab(rgb):
    def f(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    def k(t): return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = k(x), k(y), k(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def de76(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def palette(im, top=6):
    from PIL import Image
    small = im.convert("RGB").copy()
    small.thumbnail((PALETTE_SAMPLE, PALETTE_SAMPLE))
    counts = {}
    for n, rgb in small.convert("P", palette=Image.ADAPTIVE, colors=64).convert("RGB").getcolors(1 << 20):
        counts[rgb] = counts.get(rgb, 0) + n
    total = sum(counts.values()) or 1
    clusters = []
    for rgb, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        lab = srgb_to_lab(rgb)
        for cl in clusters:
            if de76(lab, cl["lab"]) <= PALETTE_DELTA:
                cl["n"] += n
                break
        else:
            clusters.append({"lab": lab, "rgb": rgb, "n": n})
    clusters.sort(key=lambda c: -c["n"])
    return [{"hex": "#%02X%02X%02X" % c["rgb"], "share": round(c["n"] / total, 4)} for c in clusters[:top]]


def scope():
    """The ruled scope, from the two records that define it. Disjoint, and measured as such."""
    designs = json.loads(DESIGN_LIST.read_text(encoding="utf-8"))
    rows = [{"path": d["path"], "sha256": d["sha256"], "size": d["size"], "set": "design_254",
             "tier": None, "tier_source": None, "grant_terms_class": None} for d in designs]
    seen = {d["sha256"] for d in designs}
    for line in S.TIERS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("sha256") in seen:
            continue
        tier = r.get("tier")
        if tier == "PRODUCTION":
            group = "production_141"
        elif tier == "REFERENCE" and REFERENCE_IN_SCOPE:
            # §BH43(b): every REFERENCE-tier asset joins the scope. Whether its bytes can be
            # rendered is a question for the render probe, never for its extension — the
            # ones no renderer opens are NAMED with their reason, not dropped in silence.
            group = "reference"
        else:
            continue
        rows.append({"path": r["relative_path"], "sha256": r.get("sha256"), "size": r.get("size"),
                     "set": group, "tier": tier, "tier_source": r.get("tier_source"),
                     "grant_terms_class": r.get("grant_terms_class")})
    return rows


def by_content(rows):
    """Group the scope by sha256: an image IS its bytes, and six pairs of the 254 are the
    same file under two paths (measured). The content is captioned once and EVERY path
    that carries it is recorded, so coverage by path stays complete and nothing is paid
    for twice."""
    groups = {}
    for r in rows:
        g = groups.setdefault(r["sha256"], dict(r, paths=[]))
        g["paths"].append(r["path"])
        if r["tier"] == "PRODUCTION":          # the stronger tier wins if two paths disagree
            g.update({k: r[k] for k in ("tier", "tier_source", "grant_terms_class", "set")})
    for g in groups.values():
        g["paths"] = sorted(g["paths"])
        g["path"] = g["paths"][0]
    return list(groups.values())


class RecordWouldShrink(RuntimeError):
    """§BH55 Phase 4 — a write that would drop captions already on disk. Raised, never warned."""


def write_tracked(record, directory=None, allow_shrink=False):
    """§BH43(a) — split the record into the tracked pair and write it deterministically.

    §BH55 PHASE 4 — IT REFUSES TO SHRINK. A caption is money already spent, and this writer rewrites the pair
    whole, so a caller holding fewer contents than the file does would silently buy back nothing and throw away
    what was bought. That is not hypothetical: `--probe` did exactly it, to all 396 rows, while printing "Nothing
    was spent". A write with fewer contents than the record already at this path raises RecordWouldShrink and
    names the loss. Monotonic, like the suite gate's floors, and it catches every path to the same loss rather
    than the one that was found. `allow_shrink` exists for a caller that MEANS to remove rows; nothing passes it
    today, and a caller that does is saying so in a diff.

    The header goes to INDEX.json; the captions go to captions.jsonl, ONE LINE PER CONTENT
    sorted by sha256, so a diff of two runs reads as the captions that changed and nothing
    else. Every line is written with sorted keys, so the same record produces the same
    bytes on every run. The per-row "path" is not stored: it is paths[0] and is derived on read,
    because a value stored twice is a value that can disagree with itself.
    """
    directory = pathlib.Path(directory or TRACKED_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    rows = sorted(record.get("captions", []), key=lambda c: c["sha256"])
    # §BH55 Phase 4 — THE FLOOR, checked before a byte is written. Counted from the file itself, not from a header
    # that could disagree with it.
    existing = directory / TRACKED_JSONL.name
    if existing.is_file() and not allow_shrink:
        held = sum(1 for line in existing.read_text(encoding="utf-8").splitlines() if line.strip())
        if len(rows) < held:
            raise RecordWouldShrink(
                "CAPTION_RECORD_WOULD_SHRINK: %s holds %d captions and this write carries %d — %d would be lost. "
                "A caption is money already spent and this writer rewrites the pair whole, so the difference is not "
                "a smaller record, it is captions deleted. The usual cause is a run that did not read the tracked "
                "record before writing it (§BH43(a): 'the rebuild reads the tracked record … so the dollar is paid "
                "once'). Nothing was written." % (existing, held, len(rows), held - len(rows)))
    lines = []
    for c in rows:
        row = {k: v for k, v in c.items() if k != "path"}
        row["paths"] = sorted(row.get("paths") or [c["path"]])
        lines.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
    header = {k: v for k, v in record.items() if k != "captions"}
    # §BH43(b): the uncaptionable list leaves the header. At REFERENCE scale it is roughly a
    # thousand entries, and an index nobody can read is not a record. Every file is still
    # named, one line each in its own sorted file; the header keeps a BY-FORMAT summary.
    unc = sorted((header.get("scope") or {}).get("uncaptionable", []), key=lambda u: u["sha256"])
    unc_lines = [json.dumps(u, ensure_ascii=False, sort_keys=True) for u in unc]
    by_format = {}
    for u in unc:
        suffix = (pathlib.Path(u["path"]).suffix or "(none)").lower()
        d = by_format.setdefault(suffix, {"count": 0, "reason": (u.get("note") or "")[:120]})
        d["count"] += 1
    if "scope" in header:
        header["scope"] = dict(header["scope"])
        header["scope"]["uncaptionable"] = len(unc)
        header["scope"]["uncaptionable_file"] = TRACKED_UNCAPTIONABLE.name
        header["scope"]["uncaptionable_by_format"] = dict(sorted(by_format.items()))
    header["record_type"] = TRACKED_RECORD_TYPE
    header["ruling"] = "%s, tracked by §BH43(a)" % (header.get("ruling") or "§BH42(b)+(c)").split(", tracked")[0]
    header["captions_file"] = TRACKED_JSONL.name
    header["captioned"] = len(rows)
    header["contents"] = len(rows)
    header["paths"] = sum(len(json.loads(l)["paths"]) for l in lines)
    header["tracked_note"] = (
        "MACHINE-WRITTEN by tools/brain/caption_scope.py. Tracked under §BH43(a) so the dollar is "
        "paid once. Keyed by content sha256; every path carrying that content is listed. Evidence "
        "of NOTHING about rights: the tier and the grant beside each row come from the tier record, "
        "which owns that question. The renders, the vectors, the model export and the SQLite index "
        "stay derived and git-ignored.")
    jsonl = ("\n".join(lines) + "\n") if lines else ""
    index = json.dumps(header, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    unc_text = ("\n".join(unc_lines) + "\n") if unc_lines else ""
    for path, text in ((TRACKED_JSONL.name, jsonl), (TRACKED_UNCAPTIONABLE.name, unc_text),
                       (TRACKED_INDEX.name, index)):
        dest = directory / path
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, dest)
    return {"directory": str(directory), "contents": len(rows), "paths": header["paths"],
            "jsonl_bytes": len(jsonl.encode("utf-8")), "index_bytes": len(index.encode("utf-8"))}


def read_tracked(directory=None):
    """The tracked record, in the one shape the rest of the brain reads. None when absent."""
    directory = pathlib.Path(directory or TRACKED_DIR)
    index, jsonl = directory / TRACKED_INDEX.name, directory / TRACKED_JSONL.name
    if not (index.is_file() and jsonl.is_file()):
        return None
    record = json.loads(index.read_text(encoding="utf-8"))
    rows = []
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        c["path"] = c["paths"][0]                      # derived, never stored twice
        rows.append(c)
    record["captions"] = rows
    unc_path = directory / TRACKED_UNCAPTIONABLE.name
    record.setdefault("scope", {})
    record["scope"] = dict(record["scope"])
    inline = record["scope"].get("uncaptionable")
    if unc_path.is_file():
        record["scope"]["uncaptionable"] = [
            json.loads(l) for l in unc_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    elif isinstance(inline, list):
        pass          # the pre-§BH43(b) shape carried the list inline; it is still the record
    else:
        record["scope"]["uncaptionable"] = []
    return record       # from here the rest of the brain sees one shape: a list of entries


def _read_record(path=None):
    """The caption record from wherever it is named: the tracked pair by default, a directory
    holding that pair, or a single JSON file in the pre-§BH43 shape. None when there is none."""
    if path is None:
        return read_tracked()
    path = pathlib.Path(path)
    if path.is_dir():
        return read_tracked(path)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def coverage(captions_path=None):
    """§BH42(e) — is every image of the ruled scope accounted for by the last caption run?

    A source added or changed since that run is reported UNCAPTIONED. A file no local
    renderer opens is UNCAPTIONABLE and is accounted for, not missing: it was seen and
    named. Nothing here is silently stale.
    """
    now = {r["sha256"]: r["path"] for r in scope()}
    record = _read_record(captions_path)
    if record is None:
        return {"state": "NO_CAPTIONS", "scope": len(now), "captioned": 0, "uncaptionable": 0,
                "uncaptioned": sorted(now.values()),
                "note": "no caption record at %s — run tools/brain/caption_scope.py --run"
                        % (captions_path or TRACKED_DIR)}
    captioned = {c["sha256"] for c in record.get("captions", [])}
    covered_paths = {q for c in record.get("captions", []) for q in (c.get("paths") or [c["path"]])}
    named = {u["sha256"] for u in (record.get("scope") or {}).get("uncaptionable", [])}
    accounted = captioned | named
    missing = sorted(now[h] for h in now if h not in accounted)
    stale = sorted(record.get("captions", [])[i]["path"] for i in range(len(record.get("captions", [])))
                   if record["captions"][i]["sha256"] not in now)
    # §BH43(b): an uncaptionable CONTENT is named once and carries every path that holds those
    # bytes, exactly as a caption row does. Counting only the first path left the second copy of
    # a duplicate reading UNCAPTIONED — the same collapse the caption rows were fixed for.
    named_paths = {q for u in (record.get("scope") or {}).get("uncaptionable", [])
                   for q in (u.get("paths") or [u["path"]])}
    all_paths = {r["path"] for r in scope()}
    missing = sorted(set(missing) | (all_paths - covered_paths - named_paths))
    return {"state": "COMPLETE" if not missing else "UNCAPTIONED",
            "scope_paths": len(all_paths), "scope_contents": len(now),
            "covered_paths": len(covered_paths & all_paths), "uncaptionable_paths": len(named_paths & all_paths),
            "captioned": len(captioned & set(now)), "uncaptionable": len(named & set(now)),
            "uncaptioned": missing, "no_longer_in_scope": stale,
            "spend_usd": record.get("spend_usd"), "model": record.get("model")}


def render(rel):
    """(image, renderer, reason) — a file no local renderer opens is UNCAPTIONABLE, named."""
    import fitz
    from PIL import Image
    src = OUTER / rel
    if pathlib.Path(rel).suffix.lower() in MOVING_SUFFIXES:
        return None, None, ("MOVING_IMAGE: %s is a video; this renderer draws still images and no "
                            "frame grabber is wired" % pathlib.Path(rel).suffix.lower())
    if pathlib.Path(rel).suffix.lower() in NOT_IMAGE_SUFFIXES:
        return None, None, "NOT_AN_IMAGE_FORMAT: %s is an archive, a font or a text format; no \
renderer was attempted" % (pathlib.Path(rel).suffix.lower() or "(no suffix)")
    try:
        doc = fitz.open(src)
        page = doc[0]
        longest = max(page.rect.width, page.rect.height) or 1.0
        scale = LONG_EDGE / longest
        pm = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        im = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
        doc.close()
        return im, "pymupdf", None
    except Exception as exc:
        first = str(exc)[:110]
    try:                              # what IS it? the bytes answer, and the reason names it
        with open(src, "rb") as fh:
            head = fh.read(4)
    except OSError:
        head = b""
    try:
        im = Image.open(src)
        im.load()
        im = im.convert("RGB")
        im.thumbnail((LONG_EDGE, LONG_EDGE))
        return im, "pillow", None
    except Exception as exc:
        if head[:4] in (b"%!PS", b"\xc5\xd0\xd3\xc6"):
            # PostScript, either plain or with a DOS EPS binary header. Neither pymupdf nor
            # pillow rasterises it without Ghostscript, which is not installed on this machine.
            # Named as one class rather than as two libraries' messages, because it is one cause
            # and one decision — installing Ghostscript is the owner's to make, not the tool's.
            return None, None, ("POSTSCRIPT_NEEDS_GHOSTSCRIPT: the bytes are PostScript (%s) and no "
                                "Ghostscript is installed, so no local renderer rasterises it"
                                % ("%!PS" if head[:4] == b"%!PS" else "DOS EPS binary header"))
        return None, None, "UNCAPTIONABLE: no local renderer opened it — pymupdf: %s; pillow: %s" % (first, str(exc)[:110])


def api_key():
    env = os.environ.get("ANTHROPIC_API_KEY")
    if env:
        return env
    for line in ENV.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*ANTHROPIC_API_KEY\s*=\s*(.+)$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("no ANTHROPIC_API_KEY in the environment or %s" % ENV)


def caption_one(client, jpeg):
    raise RuntimeError("Paid captioning is paused during the rescue until its budget integration is verified.")
    import anthropic  # noqa: F401  (imported for its side effect of being installed)
    msg = client.messages.create(
        model=MODEL, max_tokens=700,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.standard_b64encode(jpeg).decode()}},
            {"type": "text", "text": PROMPT}]}])
    body = "".join(b.text for b in msg.content if b.type == "text").strip()
    body = re.sub(r"^```(?:json)?|```$", "", body, flags=re.M).strip()
    try:
        return json.loads(body), None, msg.usage
    except Exception as exc:
        return None, "unparsed model reply: %s" % str(exc)[:80], msg.usage


def spend_of(tin, tout):
    return tin / 1e6 * RATE_IN + tout / 1e6 * RATE_OUT


def project(sample_spend, sample_images, all_images):
    """The projected total, from the sample actually paid for."""
    if sample_images <= 0:
        return 0.0
    return sample_spend / sample_images * all_images


def refuses(projected, cap, authorised):
    """§BH42(c) as a decision, so it can be checked without spending a cent.

    A projection over the cap refuses. The owner's word is the only thing that lifts it,
    and it lifts it for that run alone.
    """
    return projected > cap and not authorised


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sample", type=int, default=10, help="images to measure the cost on first")
    ap.add_argument("--run", action="store_true", help="caption the whole scope after the projection")
    ap.add_argument("--resume", action="store_true",
                    help="say so explicitly; since §BH55 Phase 4 the tracked record is read either way and the "
                         "captions already in it are never bought again")
    ap.add_argument("--probe", action="store_true",
                    help="render and name the scope, write the record, and spend NOTHING: no API call is made")
    ap.add_argument("--record", default=None,
                    help="the caption record to read and write (default: the tracked docs/design_intelligence/captions/)")
    ap.add_argument("--cap", type=float, default=DEFAULT_CAP_USD, help="the spend cap in dollars")
    ap.add_argument("--over-cap-authorised", action="store_true",
                    help="the owner's word, without which a projection over the cap refuses")
    args = ap.parse_args(argv)

    RENDERS.mkdir(parents=True, exist_ok=True)
    rows = scope()
    print("SCOPE %d images (%d design, %d production), from %s and the tier record"
          % (len(rows), sum(1 for r in rows if r["set"] == "design_254"),
             sum(1 for r in rows if r["set"] == "production_141"), DESIGN_LIST.name))

    contents = by_content(rows)
    print("CONTENTS %d distinct (%d paths; %d paths share bytes with another, measured)"
          % (len(contents), len(rows), len(rows) - len(contents)))
    rendered, uncaptionable = [], []
    t0 = time.time()
    cached = 0
    from PIL import Image as _Image
    # Measuring the palette of every cached render was the whole remaining cost of a repeat probe:
    # 3,112 hits still took 453 s. The palette is a pure function of the content, so it is cached
    # beside the render under the same ignored var/brain/ and keyed the same way.
    pal_cache = {}
    if PALETTES.is_file():
        try:
            pal_cache = json.loads(PALETTES.read_text(encoding="utf-8"))
        except ValueError:
            pal_cache = {}
    pal_dirty = False
    for n, r in enumerate(contents, 1):
        # The render file IS the cache: its name is the content's own sha, so a file that exists
        # was made from these exact bytes. Keying the cache off the RECORD was wrong — a content
        # that has been rendered but not yet captioned is in no record, so every probe re-rendered
        # the whole corpus. Measured: 12 of 3,112 hits, 703 s. On disk it is a stat() per content.
        name = r["sha256"][:16] + ".jpg"
        dest = RENDERS / name
        how = None
        if not dest.is_file():
            im, how, why = render(r["path"])
            if im is None:
                uncaptionable.append(dict(r, note=why))
                continue
            im.save(dest, "JPEG", quality=82)
        else:
            cached += 1
            how = "cached"
        # The palette is measured from the SAVED jpeg in both branches, so a cached content and a
        # freshly rendered one give the same answer rather than differing by the encoder's loss.
        pal = pal_cache.get(name)
        if pal is None:
            with _Image.open(dest) as saved:
                pal = palette(saved.convert("RGB"))
            pal_cache[name] = pal
            pal_dirty = True
        rendered.append(dict(r, render=name, renderer=how, palette=pal))
        if n % 250 == 0:
            print("   probe %d/%d  rendered=%d uncaptionable=%d  %.0f s"
                  % (n, len(contents), len(rendered), len(uncaptionable), time.time() - t0), flush=True)
    if pal_dirty:
        tmp = PALETTES.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(pal_cache, sort_keys=True), encoding="utf-8")
        os.replace(tmp, PALETTES)
    print("RENDERED %d/%d contents in %.1f s (%d taken from the existing record); "
          "%d UNCAPTIONABLE (named, not skipped)"
          % (len(rendered), len(contents), time.time() - t0, cached, len(uncaptionable)))
    for u in uncaptionable:
        print("   %s — %s" % (u["path"], u["note"]))

    client = None if args.probe else __import__("anthropic").Anthropic(api_key=api_key())
    prior, prior_per = {}, None
    prior_spend, prior_tokens = 0.0, (0, 0)
    # §BH55 Phase 4: the tracked record is ALWAYS read, never only under --resume. It was gated behind that flag,
    # and the consequence was measured the hard way: `--probe`, which makes no API call and prints "Nothing was
    # spent", loaded no prior, captioned nothing, and wrote the pair with ZERO contents over a 396-row tracked
    # record. §BH43(a)'s sentence is "the rebuild reads the tracked record and re-captions only what it does not
    # hold, so the dollar is paid once" — reading it by default is that sentence; reading it by flag was a way to
    # pay twice, or to lose the record entirely. `todo` below already excludes `prior`, so nothing else changes.
    old_record = _read_record(args.record)
    if old_record is not None:
        # §BH43(a): the prior captions come from the TRACKED record, so a machine that has
        # never captioned anything still pays nothing for what the record already holds.
        prior = {c["sha256"]: c for c in old_record.get("captions", [])}
        prior_per = old_record.get("per_image_usd")
        prior_spend = old_record.get("spend_usd") or 0.0
        prior_tokens = (old_record.get("input_tokens") or 0, old_record.get("output_tokens") or 0)
        print("%s %d contents already captioned in %s (spent $%.4f) — they are not bought again"
              % ("RESUME" if args.resume else "RECORD", len(prior), args.record or TRACKED_DIR, prior_spend))
    todo = [r for r in rendered if r["sha256"] not in prior]

    def persist(projected):
        """§BH43(a) says the dollar is paid once. A sample is PAID FOR; discarding it pays
        twice. Every exit from here writes the record through this one path — the refusal
        still refuses, it just no longer burns what it bought."""
        paths_of = {r["sha256"]: r["paths"] for r in contents}
        out = []
        for r, fields, err, usage in captions.values():
            out.append({"path": r["path"], "paths": paths_of.get(r["sha256"], [r["path"]]),
                        "sha256": r["sha256"], "set": r["set"], "tier": r["tier"],
                        "tier_source": r["tier_source"], "grant_terms_class": r["grant_terms_class"],
                        "palette": r["palette"], "caption": fields, "caption_error": err,
                        "render": r.get("render"), "renderer": r.get("renderer"),
                        "machine_written": True, "rights_note": RIGHTS_NOTE, "model": MODEL,
                        "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens})
        for sha, c in prior.items():
            if sha in captions:
                continue
            c = dict(c); c["paths"] = paths_of.get(sha, [c["path"]])
            out.append(c)
        record = {
            "record_type": "brain_captions/1.0", "ruling": "§BH42(b)+(c)", "model": MODEL,
            "scope": {"images": len(rows), "contents": len(contents), "rendered": len(rendered),
                      "duplicate_paths": len(rows) - len(contents), "uncaptionable": uncaptionable,
                      "design_list": "docs/design_intelligence/sittings/bh38/design_pdfs.json"},
            "rates_usd_per_mtok": {"input": RATE_IN, "output": RATE_OUT,
                                   "note": "the token counts are the API's own usage; these two rates are the only assumption in the spend"},
            "cap_usd": args.cap, "projected_usd": round(projected, 4),
            "captioned": len(out),
            "input_tokens": prior_tokens[0] + tin, "output_tokens": prior_tokens[1] + tout,
            "run_input_tokens": tin, "run_output_tokens": tout,
            "run_captioned": len(captions), "run_spend_usd": round(spend_of(tin, tout), 4),
            "spend_usd": round(prior_spend + spend_of(tin, tout), 4),
            "per_image_usd": round((prior_spend + spend_of(tin, tout)) / max(1, len(out)), 5),
            "spend_note": "spend_usd is every dollar spent to produce this record, carried across resumed runs; run_spend_usd is this run alone",
            "palette": "measured from the rendered pixels (ΔE76 ≤ %.0f), never asked of the model" % PALETTE_DELTA,
            "rights": RIGHTS_NOTE,
            "captions": out,
        }
        written = write_tracked(record, args.record if args.record and pathlib.Path(args.record).is_dir() else None)
        print("CAPTION_RUN captioned=%d total_spend=$%.4f this_run=$%.4f per_image=$%.5f -> %s"
              % (len(out), record["spend_usd"], record["run_spend_usd"], record["per_image_usd"],
                 written["directory"]))
        print("CAPTION_RECORD contents=%d paths=%d jsonl_bytes=%d"
              % (written["contents"], written["paths"], written["jsonl_bytes"]))
        return written

    tin = tout = 0
    captions = {}
    if args.probe:
        # §BH43(b): the probe is the half of the work that costs no money — render every content,
        # name what no renderer opens, and write the record. It makes no API call at all, so it
        # runs with no key and with no balance, and the census it banks is not lost to a later
        # failure to buy captions.
        guess = (prior_per or 0.0) * len(todo)
        print("PROBE ONLY: %d contents renderable and not yet captioned; at the last measured "
              "$%.5f each that is $%.2f against the $%.2f cap. Nothing was spent."
              % (len(todo), prior_per or 0.0, guess, args.cap))
        w = persist(guess)
        print("CAPTION_RECORD contents=%d paths=%d jsonl_bytes=%d"
              % (w["contents"], w["paths"], w["jsonl_bytes"]))
        return 0
    sample = todo[::max(1, len(todo) // max(1, args.sample))][:args.sample] if todo else []
    for r in sample:
        fields, err, usage = caption_one(client, (RENDERS / r["render"]).read_bytes())
        tin += usage.input_tokens; tout += usage.output_tokens
        captions[r["sha256"]] = (r, fields, err, usage)
    measured = spend_of(tin, tout)
    if sample:
        projected = project(measured, len(sample), len(todo))
        print("SAMPLE %d images: $%.4f measured, $%.5f each" % (len(sample), measured, measured / max(1, len(sample))))
    else:
        projected = (prior_per or 0.0) * len(todo)
        print("SAMPLE none needed: %d contents left to caption" % len(todo))
    print("PROJECTION for %d images: $%.2f against the $%.2f cap" % (len(todo), projected, args.cap))
    def keep_what_was_bought(why):
        """The sample's captions were paid for. Whatever happens next, they are kept."""
        if not captions:
            return
        w = persist(projected)
        print("SAMPLE KEPT (%s): %d contents written, $%.4f paid this run -> %s"
              % (why, len(captions), spend_of(tin, tout), w["directory"]))

    if refuses(projected, args.cap, args.over_cap_authorised):
        keep_what_was_bought("projection over the cap")
        print("SPEND_REFUSED: the projection exceeds the cap; the run does not begin without the owner's word "
              "(§BH42(c): 'do not begin the full run over the cap without my word')", file=sys.stderr)
        return 2
    if not args.run:
        keep_what_was_bought("sample only")
        print("SAMPLE ONLY — pass --run to caption the scope")
        return 0

    # §BH43(b): a long run is money on the wire. It is CHECKPOINTED, so an interruption of any
    # kind — a crash, a spent balance, a kill — costs at most the images since the last
    # checkpoint rather than the whole run. The §BH43(b)-0 fix covered the two early returns;
    # this covers the third exit, which is the one that actually took dollars with it.
    CHECKPOINT_EVERY = 100
    since_checkpoint = 0
    try:
        for i, r in enumerate(todo, 1):
            if r["sha256"] in captions:
                continue
            fields, err, usage = caption_one(client, (RENDERS / r["render"]).read_bytes())
            tin += usage.input_tokens; tout += usage.output_tokens
            captions[r["sha256"]] = (r, fields, err, usage)
            since_checkpoint += 1
            if i % 25 == 0:
                print("   %d/%d  $%.4f so far" % (i, len(todo), spend_of(tin, tout)), flush=True)
            if since_checkpoint >= CHECKPOINT_EVERY:
                persist(projected)
                since_checkpoint = 0
                print("   CHECKPOINT %d captioned, $%.4f banked" % (len(captions), spend_of(tin, tout)),
                      flush=True)
    except BaseException as exc:
        # Whatever went wrong, the captions already paid for are written before it is raised.
        persist(projected)
        print("RUN INTERRUPTED after %d captions, $%.4f paid and KEPT: %s"
              % (len(captions), spend_of(tin, tout), str(exc)[:200]), file=sys.stderr)
        raise

    persist(projected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
