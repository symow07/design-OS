"""The materials, read-only (§BH55 Phase 3, 2026-09-20).

OWNER STANDING ORDER §BH55, PHASE 3: "Every capability the engine has is reachable and labelled in words a designer
understands." The governed materials — every file of the three folders the tier record covers, each with its tier
(PRODUCTION: it may be placed in a design; REFERENCE: it may inspire, it is never placed), the owner's grant and the credit
owed where one is, what it shows (its caption) and its measured palette — were reachable only through the brain, an MCP
tool no page can call. This page reads the GOVERNED records the brain is derived from, never the brain: the tier record
(the same file, and the same override, History reads — history.tier_record_path) and the caption record
(docs/design_intelligence/captions/captions.jsonl, tracked: each caption with its measured palette; captions are
"evidence of nothing about rights" — the tier always comes from the tier record). The placement verdict is the Image
seam's own rule applied to the row (apps/ire/materials_placement.py: its codes and its credit_text). Search is by words
over the captions and the path, and by colour — ΔE76 within 12 of a measured palette colour, in image_checks' own Lab; the
brain's second, meaning-based ranking needs the brain and is not offered here. A picture is drawn, in memory, only for a
PRODUCTION row whose file's own bytes carry no other tier — the /files/ door's rule (§BH54(b)); reference bytes are never
served (§BH53(b)).
"""
from __future__ import annotations

import io
import json
import re
import threading
from functools import lru_cache
from pathlib import Path

from django.conf import settings

#: ΔE76 within which a measured palette colour matches a searched colour (the brain's own threshold)
COLOUR_MATCH_DE = 12.0
PAGE_SIZE = 40
PICTURE_EDGE = 480
DRAWN_HERE = {".jpg": "raster", ".jpeg": "raster", ".png": "raster", ".psd": "raster", ".ai": "page", ".pdf": "page"}
_HEX = re.compile(r"^#?([0-9A-Fa-f]{6})$")
_WORD = re.compile(r"[a-z0-9]+")

GRANT_WORDS = {
    "OWNER_DECLARATION": "The owner's own work — his declaration",
    "ATTRIBUTION-REQUIRED": "Free to use with a credit",
    "PERMISSIVE": "Free to use",
}

_lock = threading.Lock()
_cache: dict = {"rows": (None, []), "captions": (None, {})}


def captions_path() -> Path:
    configured = getattr(settings, "MATERIALS_CAPTIONS", None)
    if configured:
        return Path(configured)
    return Path(settings.BASE_DIR).resolve().parent / "docs" / "design_intelligence" / "captions" / "captions.jsonl"


def repo_root() -> Path:
    from apps.ire.materials_placement import REPO_ROOT
    configured = getattr(settings, "MATERIALS_REPO_ROOT", None)
    return Path(configured) if configured else REPO_ROOT


def _read_jsonl(path: Path, slot: str, build):
    """A JSON-lines record read once per change of the file (its path, size and mtime), as History reads the tier
    record; None when the file is not on this machine."""
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    with _lock:
        if _cache[slot][0] != key:
            rows = []
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
            _cache[slot] = (key, build(rows))
        return _cache[slot][1]


def tier_rows() -> list[dict] | None:
    """Every row of the tier record, in its order — keyed by its path AND its bytes: 144 hashes have more than one row
    and three carry both tiers, so a hash alone names no row. None when the record is not on this machine."""
    from apps.dashboard import history
    return _read_jsonl(history.tier_record_path(), "rows",
                       lambda rows: [r for r in rows if r.get("relative_path") and r.get("sha256")])


def captions_by_sha() -> dict:
    found = _read_jsonl(captions_path(), "captions", lambda rows: {r["sha256"]: r for r in rows if r.get("sha256")})
    return found or {}


def verdict(row: dict | None) -> dict:
    """Whether a row may be placed in a design, by the Image seam's own rule (materials_placement), in words."""
    from apps.ire import materials_placement as mp
    if row is None:
        return {"code": mp.REFUSED_NO_TIER_ROW, "placeable": False, "words": "Cannot be placed — it has no tier on record"}
    if row.get("tier") != "PRODUCTION":
        return {"code": mp.REFUSED_REFERENCE_ASSET, "placeable": False,
                "words": "A reference — it may inspire a design, it is never placed in one"}
    credit = mp.credit_text(row.get("condition") or "")
    if credit:
        return {"code": mp.PLACED, "placeable": True, "credit": credit,
                "words": "Can be placed, with its credit printed where its terms say — without it, it counts as a "
                         "reference"}
    return {"code": mp.PLACED, "placeable": True, "words": "Can be placed"}


def record_of(row) -> dict:
    """What the MATERIALS RECORD says of one offered reference, and what the file shows — read from the record the
    Materials page reads, never from the brain (§BH55 Phase 3, survey rows 1.11 and 3.9).

    Measured read-only on the development database while this was written: of the 12 material-library references this
    system has ever offered, NONE is in the tier record — the record governs 4,832 files and the picker draws from the
    design-intelligence inventory's 12,473, so a file it has never judged can be offered and approved. That is said on
    the card in those words, rather than left blank.
    """
    from apps.pipeline.services import materials_retrieval as mr
    item = str(row.library_item_id)
    if item.startswith("house:"):
        return {"words": "A house artwork from the 73-file house index — the house's own retail work, pictured from its Day 5 page preview.",
                "index": mr.facts(item.split(":", 1)[-1])}
    index = mr.facts(item.split(":", 1)[-1]) if item.startswith("materials:") else {}
    if row.image_root == "previews":
        # Day 7: offered from the library index and pictured through its preview; D-D7-1 makes the whole non-font library
        # eligible for retrieval and attachment. The tier record's placement verdict, where the file has one, is still read.
        words = "Offered from the library index (D-D7-1: house library, licensed for generation)."
        placement = {}
        rows = tier_rows() or []
        sha = item.split(":", 1)[-1]
        tiers = sorted({r.get("tier") for r in rows if r.get("sha256") == sha and r.get("tier")})
        if tiers:
            placement = {"tiers": tiers, "words": "Its tier record: " + "/".join(tiers)}
        return {"words": words, "index": index, "placement": placement}
    if row.image_root != "materials":
        return {}
    rows = tier_rows()
    if rows is None:
        return {"words": "The materials record is not on this machine, so nothing is known of this file."}
    sha = str(row.library_item_id).split(":", 1)[-1]
    path = str(row.image_path)
    found = None
    from apps.ire.materials_paths import original_material_key
    key = original_material_key(path, sha, repo_root=repo_root())
    for candidate in rows:
        if (candidate['relative_path'], candidate['sha256']) == key:
            found = candidate
            break
    if found is None:
        return {"tier": None, "words": "The materials record has not judged this file — nobody has said whether it "
                                       "may be placed in a design."}
    out = {"tier": found["tier"], "words": verdict(found)["words"]}
    # what the file shows, as the Materials page reads it: the caption's own subject sentence, never the whole record
    # (a caption is a record of fields — subject, product_form, finish, layout — not a sentence)
    caption = captions_by_sha().get(found["sha256"]) or {}
    shows = str((caption.get("caption") or {}).get("subject") or "").strip()
    if shows:
        out["shows"] = shows[:240]
    return out


def _lab(hex6: str):
    from apps.pipeline.services.image_checks import _rgb_to_lab
    return _rgb_to_lab((int(hex6[0:2], 16), int(hex6[2:4], 16), int(hex6[4:6], 16)))


def colour_distance(query_hex: str, palette: list) -> float | None:
    """The smallest ΔE76 between a searched colour and any colour of a measured palette."""
    from apps.pipeline.services.image_checks import _delta_e
    want = _lab(query_hex)
    found = [_delta_e(want, _lab(m.group(1))) for p in palette or []
             for m in [_HEX.match(str((p or {}).get("hex") or ""))] if m]
    return min(found) if found else None


def _field_words(value) -> str:
    """A caption field in words: the captioner writes one value or several (his record holds both — 237 fields of
    product_form, finish and technique are lists), and several read "tube, carton box", never as a list's brackets."""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value if v not in (None, ""))
    return str(value or "")


def _caption_words(cap: dict) -> str:
    c = cap.get("caption") or {}
    parts = [_field_words(c.get(k)) for k in ("subject", "product_form", "technique", "finish", "layout")]
    parts += [str(t) for t in (c.get("text_seen") or [])]
    parts += [str((p or {}).get("hex") or "") for p in cap.get("palette") or []]
    return " ".join(parts)


def search(tier: str = "placeable", q: str = "", colour: str = "") -> dict:
    """The rows a designer asked for: by tier ("placeable", "reference" or "all"), by words (any word longer than two
    letters, over the caption and the path; the rows with most words found first) and by colour (a measured palette
    colour within ΔE76 12; the nearest first)."""
    rows = tier_rows()
    if rows is None:
        return {"record": False, "rows": [], "counts": {}}
    caps = captions_by_sha()
    counts = {"all": len(rows), "placeable": sum(1 for r in rows if r.get("tier") == "PRODUCTION"),
              "captioned": sum(1 for r in rows if r["sha256"] in caps)}
    counts["reference"] = counts["all"] - counts["placeable"]
    words = [w for w in _WORD.findall((q or "").lower()) if len(w) > 2]
    m = _HEX.match((colour or "").strip())
    hex6 = m.group(1).upper() if m else None
    found = []
    for n, row in enumerate(rows):
        if tier == "placeable" and row.get("tier") != "PRODUCTION":
            continue
        if tier == "reference" and row.get("tier") == "PRODUCTION":
            continue
        cap = caps.get(row["sha256"])
        rank = 0.0
        if words:
            hay = (row["relative_path"] + " " + (_caption_words(cap) if cap else "")).lower()
            hits = sum(1 for w in words if w in hay)
            if not hits:
                continue
            rank -= hits
        if hex6:
            de = colour_distance(hex6, (cap or {}).get("palette"))
            if de is None or de > COLOUR_MATCH_DE:
                continue
            rank += de
        found.append((rank, row["relative_path"], n, row, cap))
    found.sort(key=lambda f: (f[0], f[1]))
    return {"record": True, "rows": [_present(n, row, cap) for _, _, n, row, cap in found], "counts": counts,
            "colour": hex6, "words": words}


def _present(n: int, row: dict, cap: dict | None) -> dict:
    path = row["relative_path"]
    folder, _, name = path.rpartition("/")
    c = (cap or {}).get("caption") or {}
    evidence = (row.get("evidence") or "").partition(" sha256:")[0]
    suffix = Path(name).suffix.lower()
    return {
        "n": n, "sha": row["sha256"], "name": name, "folder": folder.removeprefix("materials/"),
        "verdict": verdict(row), "grant": GRANT_WORDS.get(row.get("terms_class") or "", "") if
        row.get("tier") == "PRODUCTION" else "", "granted_by": row.get("granted_by") or "",
        "granted_at": row.get("granted_at") or "", "evidence": Path(evidence).name if evidence else "",
        "subject": c.get("subject") or "",
        "about": " · ".join(_field_words(c[k]) for k in ("product_form", "technique", "finish", "layout") if c.get(k)),
        "text_seen": [str(t) for t in (c.get("text_seen") or []) if t],
        "palette": [{"hex": "#" + mm.group(1).upper(), "share": round(100 * float((p or {}).get("share") or 0))}
                    for p in (cap or {}).get("palette") or [] for mm in [_HEX.match(str((p or {}).get("hex") or ""))]
                    if mm],
        "drawable": row.get("tier") == "PRODUCTION" and suffix in DRAWN_HERE,
    }


def _servable(n: int, sha: str) -> Path | None:
    """The file of row ``n`` when it may be shown: the row is PRODUCTION and named by this hash, the file lies under the
    materials root, and its OWN bytes carry no other tier (the /files/ door keys on bytes: a PRODUCTION file whose bytes
    also have a REFERENCE row is refused there, and here)."""
    from apps.dashboard import history
    rows = tier_rows() or []
    if not 0 <= n < len(rows):
        return None
    row = rows[n]
    if row.get("sha256") != sha or row.get("tier") != "PRODUCTION":
        return None
    root = repo_root().resolve()
    from apps.ire.materials_paths import resolve_material_file, MaterialPathError
    try:
        path = resolve_material_file(row['relative_path'], repo_root=root, expected_sha=sha)
    except MaterialPathError:
        return None
    try:
        path.relative_to(root / "materials")
    except ValueError:
        return None
    if not path.is_file() or history.sha256_of(path) != sha:
        return None
    if history.tiers_by_sha().get(sha) != ["PRODUCTION"]:
        return None
    return path


@lru_cache(maxsize=256)
def _drawn(path_str: str, sha: str) -> bytes | None:
    from PIL import Image
    path = Path(path_str)
    kind = DRAWN_HERE.get(path.suffix.lower())
    try:
        if kind == "page":
            import fitz
            with fitz.open(path_str, filetype="pdf") as doc:
                page = doc[0]
                scale = PICTURE_EDGE / max(page.rect.width, page.rect.height)
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        elif kind == "raster":
            im = Image.open(path_str)
            im.load()
            im = im.convert("RGB")
            im.thumbnail((PICTURE_EDGE, PICTURE_EDGE))
        else:
            return None
    except Exception:  # noqa: BLE001 — a file this machine cannot draw is shown without a picture, never an error page
        return None
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def picture_png(n: int, sha: str) -> bytes | None:
    path = _servable(n, sha)
    return _drawn(str(path), sha) if path else None


# --- Day 7 §5: the library index (D-D7-1) -----------------------------------------------------------------------------------
#: the kinds in the order the page lists them
KINDS_ORDER = ("pattern", "background", "texture", "ornament", "illustration", "icon", "logo", "typography", "palette", "layout",
               "mockup", "product-render", "photo", "dieline", "other", "font")
TIER_WORDS = {"house": "House library — licensed for generation (D-D7-1)", "GRANTED": "Granted font — licence evidence embedded",
              "excluded": "Excluded font — no licence evidence (D-D7-1)"}
SURFACE_WORDS = {"bottle-label": "bottle label", "carton": "carton", "header": "header", "riser": "riser", "base": "base", "backdrop": "backdrop",
                 "pattern-fill": "pattern fill", "ornament-accent": "ornament accent", "mockup-scene": "mockup scene", "specimen": "specimen"}
EXCLUDED_HEADING = "Excluded fonts (no licence evidence)"


def _retrieval():
    from apps.pipeline.services import materials_retrieval as mr
    return mr


def tier_of(row: dict) -> str:
    rights = row.get("rights") or {}
    return "excluded" if rights.get("excluded") else (rights.get("tier") or "house")


def index_present() -> bool:
    """Whether the library index is on this machine."""
    return _retrieval().index_path().exists()


def index_counts(items: list[dict] | None = None) -> dict:
    """Rows by kind and by tier over the whole index — the page's headline numbers."""
    from collections import Counter
    items = _retrieval().index_items() if items is None else items
    kinds = Counter(r.get("kind") or "other" for r in items)
    tiers = Counter(tier_of(r) for r in items)
    return {"all": len(items), "kinds": [(k, kinds[k]) for k in KINDS_ORDER if kinds.get(k)] + [(k, n) for k, n in sorted(kinds.items()) if k not in KINDS_ORDER],
            "tiers": dict(tiers), "captioned": sum(1 for r in items if r.get("caption_source") not in (None, "none")),
            "previews": sum(1 for r in items if r.get("preview"))}


def search_index(kind: str = "", tier: str = "", surface: str = "", q: str = "", colour: str = "") -> dict:
    """The index rows a designer asked for: by kind, by rights tier (house, GRANTED, excluded), by suitable surface, by words
    over the caption, tags, style and text seen (the file name a weaker match, said so), and by colour (ΔE76 within 12 of a
    measured colour, nearest first). Never the brain."""
    import math
    mr = _retrieval(); items = mr.index_items()
    words = [w for w in _WORD.findall((q or "").lower()) if len(w) > 2]
    m = _HEX.match((colour or "").strip()); hex6 = m.group(1).upper() if m else None
    lab = mr._hex_lab("#" + hex6) if hex6 else None
    found = []
    for row in items:
        if kind and (row.get("kind") or "other") != kind:
            continue
        if tier and tier_of(row) != tier:
            continue
        if surface and surface not in (row.get("surfaces") or []):
            continue
        rank = 0.0; de = None
        if words:
            tags = " ".join(row.get("tags") or []).lower(); style = " ".join(row.get("style") or []).lower()
            subject = (row.get("subject") or "").lower(); text = " ".join(row.get("text_seen") or []).lower(); name = (row.get("name") or "").lower()
            hits = 0.0
            for w in words:
                if w in tags or w in style:
                    hits += 3.0
                elif w in subject:
                    hits += 1.0
                elif w in text:
                    hits += 0.5
                elif w in name:
                    hits += 0.25
            if not hits:
                continue
            rank -= hits
        if lab is not None:
            best = None
            for c in row.get("colours") or []:
                if isinstance(c, dict) and c.get("lab") and (c.get("share") or 0) >= 0.02:
                    d = math.dist(lab, c["lab"]); best = d if best is None or d < best else best
            if best is None or best > COLOUR_MATCH_DE:
                continue
            de = best; rank += de
        found.append((rank, row.get("name") or "", row, de))
    found.sort(key=lambda f: (f[0], f[1]))
    return {"rows": [present_index(row, de) for _, _, row, de in found], "words": words, "colour": hex6, "n": len(found)}


_CODE = re.compile(r"^[0-9a-f]{16,}$|^[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+$")
SOURCE_WORDS = {"day7-haiku": "described by the vision model on Day 7", "day5-brain-captions": "described by the Day 5 caption run",
                "day6-font-census": "from the Day 6 font census", "none": "not described"}


def words(text) -> str:
    """Text as the page shows it — his rule: plain words, no engine code (an underscore becomes a space)."""
    return str(text or "").replace("_", " ")


def folder_words(path: str) -> str:
    """The folders of a path, less the library root and any segment that is a code (a hash, a snake name)."""
    parts = [seg for seg in path.split("/")[:-1] if seg and seg != "materials" and not _CODE.match(seg)]
    return " / ".join(words(seg) for seg in parts)


def present_index(row: dict, de: float | None = None) -> dict:
    paths = row.get("paths") or []; first = paths[0] if paths else ""
    rights = row.get("rights") or {}; tier = tier_of(row)
    return {"sha": row["sha256"], "name": row.get("name") or Path(first).name, "folder": folder_words(first),
            "kind": row.get("kind") or "other", "subject": words(row.get("subject")), "tags": [words(t) for t in (row.get("tags") or [])[:8]], "style": [words(t) for t in row.get("style") or []],
            "colours": [{"hex": c["hex"], "share": round(100 * float(c.get("share") or 0))} for c in (row.get("colours") or []) if isinstance(c, dict) and c.get("hex")][:5],
            "surfaces": [SURFACE_WORDS.get(s, s) for s in row.get("surfaces") or []], "tier": tier, "tier_words": TIER_WORDS.get(tier, tier),
            "excluded": tier == "excluded", "preview": bool(row.get("preview")) and not row.get("preview_blank"),
            "preview_blank": bool(row.get("preview_blank")), "text_seen": [words(t) for t in (row.get("text_seen") or [])[:4]],
            "caption_source": row.get("caption_source"), "described": SOURCE_WORDS.get(row.get("caption_source") or "none", "described"),
            "family": words(row.get("family")), "faces": len(row.get("faces") or []) if row.get("kind") == "font" else None,
            "arabic": row.get("arabic"), "paths": len(paths), "de": None if de is None else round(de, 1), "basis": words(rights.get("basis"))}


def detail(sha: str) -> dict | None:
    """Everything the index says of one file, its placement tier where the tier record has one, and its previews."""
    row = _retrieval().index_row(sha)
    if not row:
        return None
    out = dict(row); out["card"] = present_index(row)
    out["category_words"] = words(row.get("inventory_category")).lower()
    out["file_names"] = sorted({Path(p).name for p in row.get("paths") or []})
    out["text_seen_words"] = [words(t) for t in row.get("text_seen") or []]
    out["evidence_words"] = {k: words(v) for k, v in ((row.get("rights") or {}).get("evidence") or {}).items()} if (row.get("rights") or {}).get("evidence") else None
    out["faces_words"] = [{"full_name": words(f.get("full_name")), "weight_class": f.get("weight_class"), "italic": f.get("italic"), "scripts": f.get("scripts") or []}
                          for f in row.get("faces") or []]
    tiers = sorted({r.get("tier") for r in (tier_rows() or []) if r.get("sha256") == sha and r.get("tier")})
    out["placement"] = {"tiers": tiers, "words": ("Its tier record: " + "/".join(tiers) + " — placement law (materials_placement) reads that record; "
                                                "D-D7-1 governs retrieval and attachment") if tiers else "Not in the tier record; D-D7-1 governs retrieval and attachment"}
    out["preview_file"] = preview_file(sha) is not None and not row.get("preview_blank")
    return out


def preview_file(sha: str) -> Path | None:
    """The Day 7 preview of an indexed file (hash-named PNG under the previews root) — only for a hash the index names."""
    if not re.fullmatch(r"[0-9a-f]{64}", sha or "") or _retrieval().index_row(sha) is None:
        return None
    root = _retrieval().previews_root().resolve(); path = (root / (sha + ".png")).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path if path.is_file() else None
