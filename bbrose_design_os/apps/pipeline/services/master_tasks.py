"""D-D11-9 — a finished product master published as a real design task in the app, so its own design page
(/dashboard/designs/<id>/) shows every surface, the sticker or panels, the carton and the downloads: his goal of
2026-10-13, (5) "one 'Download' (the layered .ai, with other formats in a small menu)" and (6) every drawing large, with
click-to-enlarge, zoom and pan.

``publish(manifest)`` reads a manifest that names the product, the target, the surfaces (each its title, its picture,
the page of its print file the drawing shows, its layered file and its other files) and the day's records as evidence.
It refuses the whole manifest — every problem named — BEFORE anything is written, where a file is missing, unreadable
or not what its slot holds. It builds ONE drawing, a PDF with a page per surface taken from the product's own pieces
(PyMuPDF, local), so the page's viewer pages through every surface — each page carrying its own file's layers, the
hidden ones hidden — and draws every page of it beside its own file's page: a page that does not draw the same is
refused too, before anything is written. Then it copies every file under MEDIA_ROOT (``dielines/day11/<slug>/``), each
pinned by its sha256 in a record kept beside them (``publication.json``), writes the drawing, and creates or updates ONE
design task at Gate 2, never past it. Approving it is the owner's own click (§BH55 clause 6, §BH54(b): acceptance is his
act, with his identity, the time and the hash), so nothing here writes an approval, a gate decision or an acceptance,
and a design he has already decided on is never published over.

Publishing the same manifest again updates the same task (found by its key in ``options``) and its one output in place;
a copy whose bytes are already the ones pinned is left untouched, so the drawing's fingerprint, and with it the named
views, survives a re-publish. No paid call is made or reachable from here: no image, no model, no ledger.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings

REPO = Path(settings.BASE_DIR).parent
#: the manifest this reads, and the record it writes beside the copies
MANIFEST_SCHEMA = "master_task_manifest/1"
RECORD_SCHEMA = "master_task_publication/1"
RECORD_NAME = "publication.json"
#: where a product's copies live, under MEDIA_ROOT — outside ``dielines/hybrid`` (the files door refuses that folder)
#: and outside every REFERENCE-class folder (§BH54(b)), so ``/files/`` serves them
MEDIA_FOLDER = "dielines/day11"
#: the task's options: the key a re-publish finds its task by, and the words a marked test's own page carries
KEY_OPTION = "master_task_key"
TEST_WORDS_OPTION = "test_words"
#: the targets a master is published as (the lead's decision of Day 11): the palettes as 'palette', the lipstick as
#: 'packaging' — never 'product_container', whose page needs a container contract nobody gave (serializers.py VQR-6)
TARGETS = ("palette", "packaging")
#: the one state it is built at: the owner's Approve click makes it 'completed' (Gate2ApproveView, resume_after_gate_2)
AWAITING = "awaiting_gate_2"
#: what the output's spec_sheet calls this kind of output — none of the backends the page or Gate 2 branch on
#: (hybrid_bottle, hybrid_assembly, container, artwork)
BACKEND = "master_publication"
#: the spec_sheet's keys: the pins and surfaces, and the files offered under "Other formats"
#: (``PackagingOutputSerializer.get_other_files``)
SPEC_KEY = "master_task/1.0"
DOWNLOADS_KEY = "downloads/1.0"
#: the words its page says its two fixed files in (static/js/gates.js reads them for this backend): the one Download is
#: the primary surface's own layered file, and the drawing is every surface, a page each — never the words of a
#: one-surface carton's files ("every piece its own", "one layer")
SLOT_WORDS_KEY = "slot_words/1.0"
DRAWING_WORDS = "Every surface, a page each"
#: the provenance kind of its one picture — never ``authored_master_snapshot``, which the serializer hides outside the
#: authored masters' own pages
PROVENANCE_KIND = "master_publication"
#: the folders inside ``<slug>/`` that are not surfaces
HERO_DIR, CONCEPT_DIR, EVIDENCE_DIR = "hero", "concept", "evidence"
RESERVED_KEYS = (HERO_DIR, CONCEPT_DIR, EVIDENCE_DIR)
#: the combined drawing's file name after the slug: a PDF-compatible .ai, as the drawings of 124 and 125 are
DRAWING_SUFFIX = "-every-surface.ai"
#: a copy is written beside its place under this suffix, then moved into it whole
PART_SUFFIX = ".part"
HASH_CHUNK_BYTES = 1 << 20
#: the brand every master is published under (as hybrid_views does)
BRAND_NAME = "BBROSE"
#: palettes and a lipstick are cosmetics (core.models.PRODUCT_CATEGORIES)
PRODUCT_CATEGORY = "CO"
#: the core Product's own limits (core.models.Product: product_id 50, name and name_ar 200)
PRODUCT_ID_MAX, PRODUCT_NAME_MAX = 50, 200
#: the picture's direction words (GeneratedImage.direction_name, 200) and a test's words beside the page's title
DIRECTION_MAX, TEST_WORDS_MAX = 200, 40
#: a slug or a surface key: lower-case words joined by hyphens, a folder name and a key at once — matched WHOLE
#: (``fullmatch``): ``match`` lets a trailing newline past the ``$`` into a folder name and a task key
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,47}$")
#: the scale each page of the one drawing is drawn at beside its own file's page (1 = 72 dpi): every pixel must agree
PROOF_SCALE = 1.0
#: the key each copied layer is marked with, the drawing's page number its value: PyMuPDF's ``garbage=3`` merges
#: objects of the same text, so two surfaces' layers of one name (the lid's 'foil' shown, the box's hidden) would
#: otherwise become ONE layer with one state, and one of the two pages would draw wrong
LAYER_PAGE_KEY = "BBROSEPage"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
#: the files a manifest may name, and how each is said in the "Other formats" menu (Day 10's words)
WORDS = {".png": "picture", ".pdf": "PDF", ".ai": "layered file (.ai)", ".json": "record", ".svg": "drawing (SVG)"}
PAGE_SUFFIXES = (".pdf", ".ai")
LAYERED_SUFFIXES = (".ai",)
PICTURE_SUFFIXES = (".png",)
MANIFEST_KEYS = {"schema", "slug", "target", "task_text", "product", "concept", "hero", "primary", "surfaces",
                 "evidence", "test_words"}
PRODUCT_KEYS = {"product_id", "name", "name_ar", "year"}
CONCEPT_KEYS = {"picture", "direction", "owner_picked"}
SURFACE_KEYS = {"key", "title", "picture", "page", "layered", "others"}
PAGE_KEYS = {"file", "number"}
EVIDENCE_KEYS = {"file", "words"}
#: what the prompt field of its one picture says: it was not drawn by this task
NOT_DRAWN = ("Not drawn by this design task: the finished master, published from the day's own files and records by "
             "master_tasks.publish. No image call.")


class Refused(ValueError):
    """A manifest refused before anything was written; ``problems`` names each thing wrong with it."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("The manifest is refused, nothing was written: " + "; ".join(self.problems))


class Changed(Exception):
    """A pinned copy that is gone or is no longer the bytes published."""


def _sha(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source(value) -> Path:
    """A manifest's file: absolute as given, else read from the repository's root (``docs/audit/day-11/...``)."""
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def _is_png(path: Path) -> bool:
    with open(path, "rb") as source:
        return source.read(len(PNG_MAGIC)) == PNG_MAGIC


def _page_count(path: Path):
    """How many pages the file holds, read as a PDF (a PDF-compatible .ai is one); None where its bytes are not one."""
    import fitz
    try:
        pdf = fitz.open(str(path), filetype="pdf")
    except (fitz.FileDataError, RuntimeError, ValueError):
        return None
    with pdf:
        return pdf.page_count


def _words(title: str, name: str) -> str:
    return "%s — %s, %s" % (title, name, WORDS[Path(name).suffix.lower()])


class _Plan:
    """The manifest read and every file checked: nothing is written until all of it holds."""

    def __init__(self):
        self.problems = []
        self.copies = {}        # rel (under MEDIA_ROOT) -> (source Path, sha256)
        self.pages = []         # (source Path, page number, words)
        self.downloads = []     # {"path": rel, "words"}
        self.evidence = []      # {"path": rel, "words", "source"}

    def file(self, where: str, value, suffixes) -> Path | None:
        """One file the manifest names, checked: a string, there, a file, of a kind its slot holds."""
        if not isinstance(value, str) or not value.strip():
            self.problems.append("%s names no file" % where)
            return None
        path = _source(value)
        if not path.is_file():
            self.problems.append("%s: %s is not there" % (where, value))
            return None
        if path.suffix.lower() not in suffixes:
            self.problems.append("%s: %s is not a %s" % (where, value, " or ".join(suffixes)))
            return None
        if path.suffix.lower() == ".png" and not _is_png(path):
            self.problems.append("%s: %s is not a PNG picture" % (where, value))
            return None
        return path

    def copy(self, where: str, source: Path, rel: str) -> str:
        """Where the file is copied to: a file named twice (a sticker's .ai as its page and its layered file, a tray's
        PDF for its artwork and its cut page) is copied once, where it was first named; two different files bound for
        one place are refused, never one of them lost."""
        for kept, (already, _sha256) in self.copies.items():
            if already.resolve() == source.resolve():
                return kept
        if rel in self.copies:
            self.problems.append("%s: %s would land on %s, where %s already goes" % (
                where, source, rel, self.copies[rel][0]))
            return rel
        self.copies[rel] = (source, _sha(source))
        return rel

    def offer(self, rel: str, words: str, shown) -> None:
        """A file offered under "Other formats", once, unless it is shown in a slot of its own."""
        if rel not in shown and all(row["path"] != rel for row in self.downloads):
            self.downloads.append({"path": rel, "words": words})


def _text(plan: _Plan, where: str, value, limit) -> str:
    """A value that must be words: not empty, and no longer than its field holds (``limit``; None for a text field)."""
    if not isinstance(value, str) or not value.strip():
        plan.problems.append("%s is empty" % where)
        return ""
    if limit is not None and len(value) > limit:
        plan.problems.append("%s is longer than %d characters" % (where, limit))
    return value.strip()


def _keys(plan: _Plan, where: str, value, keys: set) -> bool:
    """The block is a dict with exactly the keys it must have: a missing one is refused, so is one this does not read."""
    if not isinstance(value, dict):
        plan.problems.append("%s is not a block of named values" % where)
        return False
    missing, unknown = sorted(keys - set(value)), sorted(set(value) - keys)
    if missing:
        plan.problems.append("%s lacks %s" % (where, ", ".join(missing)))
    if unknown:
        plan.problems.append("%s carries %s, which this does not read" % (where, ", ".join(unknown)))
    return not missing


def read(manifest) -> dict:
    """The manifest, checked whole: every value, every file (there, of its kind, a picture a PNG, a page inside its
    file), every copy's place, and the one drawing built in memory with each of its pages drawn beside its own file's
    page (``_drawing``, ``_unlike``). Raises ``Refused`` naming every problem; reads files, writes nothing."""
    plan = _Plan()
    if not _keys(plan, "The manifest", manifest, MANIFEST_KEYS):
        raise Refused(plan.problems)
    if manifest["schema"] != MANIFEST_SCHEMA:
        plan.problems.append("the manifest's schema is %r, not %r" % (manifest["schema"], MANIFEST_SCHEMA))
    slug = manifest["slug"]
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        raise Refused(plan.problems + ["the slug %r is not lower-case words joined by hyphens" % (slug,)])
    folder = "%s/%s" % (MEDIA_FOLDER, slug)
    if manifest["target"] not in TARGETS:
        plan.problems.append("the target %r is not one of %s" % (manifest["target"], ", ".join(TARGETS)))
    task_text = _text(plan, "task_text", manifest["task_text"], None)
    test_words = manifest["test_words"]
    if test_words is not None:
        test_words = _text(plan, "test_words", test_words, TEST_WORDS_MAX)

    product = {}
    if _keys(plan, "product", manifest["product"], PRODUCT_KEYS):
        given = manifest["product"]
        product = {"product_id": _text(plan, "product.product_id", given["product_id"], PRODUCT_ID_MAX),
                   "name": _text(plan, "product.name", given["name"], PRODUCT_NAME_MAX),
                   "name_ar": given["name_ar"], "year": given["year"]}
        if not isinstance(given["name_ar"], str) or len(given["name_ar"]) > PRODUCT_NAME_MAX:
            plan.problems.append("product.name_ar is not a name (it may be empty)")
        if not isinstance(given["year"], int) or isinstance(given["year"], bool):
            plan.problems.append("product.year is not a year")

    concept = {}
    if _keys(plan, "concept", manifest["concept"], CONCEPT_KEYS):
        given = manifest["concept"]
        picture = plan.file("concept.picture", given["picture"], PICTURE_SUFFIXES)
        concept = {"direction": _text(plan, "concept.direction", given["direction"], DIRECTION_MAX),
                   "owner_picked": given["owner_picked"],
                   "picture": picture and plan.copy("concept.picture", picture, "%s/%s/%s" % (
                       folder, CONCEPT_DIR, picture.name))}
        if not isinstance(given["owner_picked"], bool):
            plan.problems.append("concept.owner_picked is not true or false")

    hero = plan.file("hero", manifest["hero"], PICTURE_SUFFIXES)
    hero_rel = hero and plan.copy("hero", hero, "%s/%s/%s" % (folder, HERO_DIR, hero.name))

    surfaces = manifest["surfaces"]
    if not isinstance(surfaces, list) or not surfaces:
        raise Refused(plan.problems + ["the manifest names no surface"])
    keys = [s["key"] for s in surfaces if isinstance(s, dict) and "key" in s]
    native_rel = None
    named = []
    for n, surface in enumerate(surfaces, start=1):
        where = "surface %d" % n
        if not _keys(plan, where, surface, SURFACE_KEYS):
            continue
        key = surface["key"]
        if not isinstance(key, str) or not SLUG.fullmatch(key) or key in RESERVED_KEYS or keys.count(key) > 1:
            plan.problems.append("%s: its key %r is not a fresh lower-case word (nor hero, concept, evidence)" % (
                where, key))
            continue
        where = "the surface %s" % key
        title = _text(plan, "%s's title" % where, surface["title"], PRODUCT_NAME_MAX)
        named.append({"key": key, "title": title})
        here = "%s/%s" % (folder, key)
        page = surface["page"]
        if _keys(plan, "%s's page" % where, page, PAGE_KEYS):
            source = plan.file("%s's page" % where, page["file"], PAGE_SUFFIXES)
            number = page["number"]
            if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                plan.problems.append("%s's page number %r is not a page" % (where, number))
            elif source is not None:
                count = _page_count(source)
                if count is None:
                    plan.problems.append("%s's page: %s does not open as a PDF" % (where, page["file"]))
                elif number > count:
                    plan.problems.append("%s's page %d is past the %d page(s) of %s" % (
                        where, number, count, page["file"]))
                else:
                    plan.pages.append((source, number, title))
                    named[-1]["page_file"] = plan.copy("%s's page" % where, source, "%s/%s" % (here, source.name))
        if surface["layered"] is not None:
            layered = plan.file("%s's layered file" % where, surface["layered"], LAYERED_SUFFIXES)
            if layered is not None:
                named[-1]["layered"] = plan.copy("%s's layered file" % where, layered, "%s/%s" % (here, layered.name))
                if key == manifest["primary"]:
                    native_rel = named[-1]["layered"]
        if surface["picture"] is not None:
            picture = plan.file("%s's picture" % where, surface["picture"], PICTURE_SUFFIXES)
            if picture is not None:
                named[-1]["picture"] = plan.copy("%s's picture" % where, picture, "%s/%s" % (here, picture.name))
        others = surface["others"]
        if not isinstance(others, list):
            plan.problems.append("%s's others is not a list of files" % where)
            others = []
        named[-1]["others"] = []
        for m, value in enumerate(others, start=1):
            other = plan.file("%s's other file %d" % (where, m), value, tuple(WORDS))
            if other is not None:
                named[-1]["others"].append(plan.copy("%s's other file %d" % (where, m), other,
                                                     "%s/%s" % (here, other.name)))
    if manifest["primary"] not in keys:
        plan.problems.append("the primary %r names no surface" % (manifest["primary"],))
    elif native_rel is None:
        plan.problems.append("the primary surface %r has no layered .ai: the one Download would be missing" % (
            manifest["primary"],))

    evidence = manifest["evidence"]
    if not isinstance(evidence, list):
        plan.problems.append("evidence is not a list of records")
        evidence = []
    for n, row in enumerate(evidence, start=1):
        where = "evidence %d" % n
        if not _keys(plan, where, row, EVIDENCE_KEYS):
            continue
        source = plan.file(where, row["file"], tuple(WORDS))
        words = _text(plan, "%s's words" % where, row["words"], PRODUCT_NAME_MAX)
        if source is not None:
            rel = plan.copy(where, source, "%s/%s/%s-%s" % (folder, EVIDENCE_DIR, source.parent.name, source.name))
            plan.evidence.append({"path": rel, "words": words, "source": str(row["file"])})

    if plan.problems:
        raise Refused(plan.problems)
    # the one drawing, built here so a page it cannot draw as its own file draws is refused before anything is written
    drawing_rel = "%s/%s%s" % (folder, slug, DRAWING_SUFFIX)
    drawing, problems = _drawing(plan.pages, "%s — every surface" % product["name"])
    if not problems:
        problems = _unlike(plan.pages, drawing)
    if problems:
        raise Refused(problems)
    primary_title = next(s["title"] for s in named if s["key"] == manifest["primary"])
    slot_words = {"native_ai": _words(primary_title, Path(native_rel).name),
                  "design_preview_ai": "%s — %s" % (DRAWING_WORDS, Path(drawing_rel).name)}
    # the one Download is the layered file; the drawing and the hero have slots of their own; every other file once
    shown = {native_rel, hero_rel}
    for surface in named:
        for rel in [surface.get("layered"), surface.get("page_file")] + surface["others"] + [surface.get("picture")]:
            if rel is not None:
                plan.offer(rel, _words(surface["title"], Path(rel).name), shown)
    for row in plan.evidence:
        plan.offer(row["path"], "%s — %s, %s" % (row["words"], Path(row["path"]).name, WORDS[
            Path(row["path"]).suffix.lower()]), shown)
    return {"slug": slug, "folder": folder, "target": manifest["target"], "task_text": task_text,
            "test_words": test_words, "product": product, "concept": concept, "hero": hero_rel, "native": native_rel,
            "surfaces": named, "pages": plan.pages, "copies": plan.copies, "downloads": plan.downloads,
            "evidence": plan.evidence, "drawing": drawing_rel, "drawing_bytes": drawing, "slot_words": slot_words,
            "manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode(
                "utf-8")).hexdigest()}


def _decided(task) -> list:
    """What the owner has already done to the design, in words: a design he decided on is never published over (his
    acceptance names the preview's bytes, and a new publication would change them under it)."""
    from apps.pipeline.models import GateDecision
    said = []
    if task.status != AWAITING:
        said.append("design %d stands at %r, not at Gate 2" % (task.pk, task.status))
    if task.packaging_outputs.filter(is_final_approved=True).exists():
        said.append("design %d has an approved output" % task.pk)
    if GateDecision.objects.filter(task=task, gate="gate_2").exists():
        said.append("design %d has a Gate 2 decision on record" % task.pk)
    if task.design_acceptances.exists():
        said.append("design %d carries the owner's own act on its design" % task.pk)
    return said


def _write(dest: Path, data_from, sha: str) -> bool:
    """One copy written whole — beside its place first, then moved in — and its bytes checked against the pin. A copy
    already holding the pinned bytes is left as it is (its time with it). True where it was written."""
    if dest.is_file() and _sha(dest) == sha:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + PART_SUFFIX)
    if isinstance(data_from, bytes):
        part.write_bytes(data_from)
    else:
        shutil.copyfile(data_from, part)
    if _sha(part) != sha:
        raise Changed("%s changed while it was copied: its bytes are not the ones read" % data_from)
    os.replace(part, dest)
    return True


def _which_page(source: Path, number: int, words: str) -> str:
    return "the page of %s (%s, page %d)" % (words, source.name, number)


def _layer_xrefs(out) -> set:
    """Every layer (optional content group) the drawing holds so far, by its object number."""
    return {xref for xref in range(1, out.xref_length()) if out.xref_get_key(xref, "Type") == ("name", "/OCG")}


def _tag(out, xref: int, n: int) -> None:
    """A copied layer marked as page ``n``'s own (``LAYER_PAGE_KEY``), so no other page's layer is merged into it."""
    out.xref_set_key(xref, LAYER_PAGE_KEY, str(n))


def _layers_of(out, piece, before: set, n: int, which: str, problems: list) -> list:
    """The layers page ``n`` brought into ``out`` (those not in ``before``), each with the state its own file gives it:
    ``[(xref, shown)]`` in object order. ``insert_pdf`` copies a page's layers but not its file's /OCProperties, so
    without these every hidden layer draws. A copied layer is known by its name in its own file; a layer its file does
    not list is drawn by its file — a file with no /OCProperties hides nothing (the 1 : 1 sheets of Day 10 and 11 hold
    the box's 'artwork', 'cut' and 'crease' so) — and is carried shown; a name its file holds both shown and hidden
    cannot be carried, and the page is refused by name. ``_unlike`` then proves every page against its own file."""
    states = {}
    for xref, info in piece.get_ocgs().items():
        states.setdefault(piece.xref_get_key(xref, "Name"), set()).add(bool(info["on"]))
    rows = []
    for xref in sorted(_layer_xrefs(out) - before):
        name = out.xref_get_key(xref, "Name")
        if name not in states:
            _tag(out, xref, n)
            rows.append((xref, True))
            continue
        if len(states[name]) != 1:
            problems.append("%s carries two layers named %r, one shown and one hidden: the one drawing cannot tell "
                            "them apart — give its print PDF's page instead" % (which, name[1]))
            continue
        _tag(out, xref, n)
        rows.append((xref, next(iter(states[name]))))
    return rows


def _pdf_text(words: str) -> str:
    """Words as a PDF text string (UTF-16BE, hex), whatever their script."""
    return "<FEFF%s>" % words.encode("utf-16-be").hex().upper()


def _ocproperties(out, groups: list) -> None:
    """The drawing's layers as their own files have them: every copied layer listed, the hidden ones OFF, and the
    layers panel a group per surface under its title. Nothing is written where no page brought a layer."""
    rows = [row for _words_, group in groups for row in group]
    if not rows:
        return
    refs = " ".join
    order = " ".join("[%s %s]" % (_pdf_text(words), refs("%d 0 R" % xref for xref, _shown in group))
                     for words, group in groups)
    out.xref_set_key(out.pdf_catalog(), "OCProperties", "<</OCGs[%s]/D<</ON[%s]/OFF[%s]/Order[%s]/RBGroups[]>>>>" % (
        refs("%d 0 R" % xref for xref, _shown in rows),
        refs("%d 0 R" % xref for xref, shown in rows if shown),
        refs("%d 0 R" % xref for xref, shown in rows if not shown), order))


def _drawing(pages, title: str):
    """The one drawing, ``(bytes, problems)``: a page per surface, each the named page of the surface's own file, in
    the manifest's order, carrying its own file's layers in the states its file gives them (``_layers_of``,
    ``_ocproperties``). Its metadata is fixed and no new /ID is drawn, so the same pieces make the same bytes."""
    import fitz
    problems, groups = [], []
    out = fitz.open()
    for n, (source, number, words) in enumerate(pages, start=1):
        with fitz.open(str(source), filetype="pdf") as piece:
            before = _layer_xrefs(out)
            out.insert_pdf(piece, from_page=number - 1, to_page=number - 1)
            rows = _layers_of(out, piece, before, n, _which_page(source, number, words), problems)
        if rows:
            groups.append((words, rows))
    _ocproperties(out, groups)
    out.set_metadata({"title": title, "author": BRAND_NAME, "creator": "BBROSE Design OS (master_tasks.publish)",
                      "producer": "PyMuPDF", "subject": "", "keywords": "", "creationDate": "", "modDate": ""})
    data = out.tobytes(garbage=3, deflate=True, no_new_id=True)
    out.close()
    return data, problems


def _differing(own, made) -> int:
    """How many pixels of two drawings of a page differ; every one where their sizes differ."""
    if (own.width, own.height) != (made.width, made.height):
        return max(own.width * own.height, made.width * made.height)
    a, b, step = own.samples, made.samples, own.n
    return sum(1 for i in range(0, len(a), step) if a[i:i + step] != b[i:i + step])


def _unlike(pages, data: bytes) -> list:
    """Each page of the drawing drawn beside its own file's page, at ``PROOF_SCALE``: a page whose pixels are not all
    the same, in words. The drawing's views and its every-surface download are drawn from this file, so a page that
    draws other than its own file — a hidden layer shown, a mask over the art — is never published."""
    import fitz
    matrix = fitz.Matrix(PROOF_SCALE, PROOF_SCALE)
    unlike = []
    with fitz.open(stream=data, filetype="pdf") as drawing:
        for n, (source, number, words) in enumerate(pages, start=1):
            with fitz.open(str(source), filetype="pdf") as piece:
                own = piece[number - 1].get_pixmap(matrix=matrix, alpha=False)
            made = drawing[n - 1].get_pixmap(matrix=matrix, alpha=False)
            if own.samples != made.samples or (own.width, own.height) != (made.width, made.height):
                unlike.append("%s does not draw in the one drawing as it draws in its own file (%d of %d pixels "
                              "differ at 72 dpi): give its print PDF's page instead" % (
                                  _which_page(source, number, words), _differing(own, made), own.width * own.height))
    return unlike


def _product_on_record(plan: dict, brand):
    """The core Product the page's title is read from (``board.title_of``), found by its id; None where there is none.
    A product on record under that id is never renamed or moved to another brand: the manifest is refused instead.
    Its id is what the page shows as the design's SKU (``DesignTask.sku_on_record``), so the manifest names it."""
    from apps.core.models import Product
    found = Product.objects.filter(product_id=plan["product"]["product_id"]).first()
    if found is not None and (found.brand_id != brand.pk or found.name != plan["product"]["name"]):
        raise Refused(["the product record %r is %r of brand %d; a publication never renames it" % (
            found.product_id, found.name, found.brand_id)])
    return found


def _product(plan: dict, brand):
    """The product on record (``_product_on_record``), else one made with the manifest's name — in development."""
    from apps.core.models import Product
    found = _product_on_record(plan, brand)
    if found is not None:
        return found
    given = plan["product"]
    return Product.objects.create(brand=brand, product_id=given["product_id"], name=given["name"],
                                  name_ar=given["name_ar"], category=PRODUCT_CATEGORY, year=given["year"],
                                  status="in_development")


def _options(plan: dict, before: dict) -> dict:
    """The task's options: every paid call refused (``spend_held``), its key, and — for a test — the test marking the
    board folds it by and the words its own page carries."""
    from apps.dashboard.board import TEST_RUN_OPTION
    options = dict(before)
    options.update({"spend_held": True, KEY_OPTION: plan["slug"]})
    for name in (TEST_RUN_OPTION, TEST_WORDS_OPTION):
        options.pop(name, None)
    if plan["test_words"] is not None:
        options.update({TEST_RUN_OPTION: True, TEST_WORDS_OPTION: plan["test_words"]})
    return options


def _named(source: Path) -> str:
    """A source as the record names it: from the repository's root where it lies inside it (``docs/audit/...``)."""
    return str(source.relative_to(REPO)) if source.is_relative_to(REPO) else str(source)


def _pins(plan: dict, drawing_sha: str) -> dict:
    """Every copy's sha256 and where it was copied from; the drawing's, with the pages it was built from."""
    pins = {rel: {"source": _named(source), "sha256": sha} for rel, (source, sha) in plan["copies"].items()}
    pins[plan["drawing"]] = {"source": "built from %d page(s) of the surfaces' own files" % len(plan["pages"]),
                             "sha256": drawing_sha}
    return pins


def record_path(slug: str) -> Path:
    return Path(settings.MEDIA_ROOT) / MEDIA_FOLDER / slug / RECORD_NAME


def publish(manifest) -> dict:
    """The master as a design task at Gate 2: the manifest read and checked whole (``read``), every file copied and
    pinned, the one drawing built, the task, its one picture and its one output written in one transaction, the
    drawing's views named by surface and their pictures made, and the record written beside the copies. Returns what
    was published: ``{"task_id", "output_id", "created", "url", "record", "views", "written"}``."""
    from django.db import transaction

    from apps.core.models import Brand
    from apps.pipeline import drawing_views
    from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput

    plan = read(manifest)
    brand = Brand.objects.filter(name__iexact=BRAND_NAME).first()
    if brand is None:
        raise Refused(["the %s brand record is missing" % BRAND_NAME])
    task = DesignTask.objects.filter(**{"options__%s" % KEY_OPTION: plan["slug"]}).order_by("pk").first()
    if task is not None and _decided(task):
        raise Refused(_decided(task))
    _product_on_record(plan, brand)

    media = Path(settings.MEDIA_ROOT)
    written = [rel for rel, (source, sha) in plan["copies"].items() if _write(media / rel, source, sha)]
    drawing = plan["drawing_bytes"]          # built and drawn beside every page's own file by ``read``
    drawing_sha = hashlib.sha256(drawing).hexdigest()
    if _write(media / plan["drawing"], drawing, drawing_sha):
        written.append(plan["drawing"])
    pins = _pins(plan, drawing_sha)

    with transaction.atomic():
        created = task is None
        if created:
            # made at 'queued' and moved to Gate 2 by an update, inside this one transaction: nobody sees it queued,
            # and the move fans out no notification or e-mail to every reviewer (signals.py — QuerySet.update)
            task = DesignTask.objects.create(brand=brand, task_text=plan["task_text"], design_target=plan["target"],
                                             status="queued", created_by=None, options={})
        else:
            task = DesignTask.objects.select_for_update().get(pk=task.pk)
            if _decided(task):
                raise Refused(_decided(task))
        task.product = _product(plan, brand)
        task.task_text, task.design_target = plan["task_text"], plan["target"]
        task.options = _options(plan, task.options if isinstance(task.options, dict) else {})
        task.save(update_fields=["product", "task_text", "design_target", "options", "updated_at"])
        if created:
            DesignTask.objects.filter(pk=task.pk).update(status=AWAITING)
            task.status = AWAITING
        output = task.current_output()
        concept = plan["concept"]
        image_fields = {"direction_name": concept["direction"], "prompt_used": NOT_DRAWN,
                        "image_file": concept["picture"], "is_approved": concept["owner_picked"], "qa_passed": False,
                        "variation_number": 1, "superseded": False,
                        "reference_provenance": {"kind": PROVENANCE_KIND, "slug": plan["slug"],
                                                 "sha256": pins[concept["picture"]]["sha256"]}}
        if output is None:
            image = GeneratedImage.objects.create(task=task, **image_fields)
            output = PackagingOutput(task=task, approved_image=image, spec_sheet={})
        else:
            image = output.approved_image
            for name, value in image_fields.items():
                setattr(image, name, value)
            image.save()
        output.design_preview = plan["hero"]
        output.design_preview_ai = plan["drawing"]
        path = drawing_views.drawing_file(output)
        spec = dict(output.spec_sheet)       # a JSON field never null; a new output is made with {}
        spec.update({
            "backend": BACKEND,
            "native_ai/1.0": {"built": True, "path": plan["native"]},
            SLOT_WORDS_KEY: plan["slot_words"],
            DOWNLOADS_KEY: plan["downloads"],
            # the drawing's pages named by surface, kept with its fingerprint (``drawing_views.views_for`` reads them
            # back while the file is the one written; a touched file falls back to its generic page names)
            "drawing_views/1.0": {"schema": "drawing_views/1.0", "sections": [],
                                  "views": [{"key": "page-%d" % n, "words": words, "page": n, "box_mm": None}
                                            for n, (_source_, _number, words) in enumerate(plan["pages"], start=1)],
                                  "drawing": drawing_views._fingerprint(path)},
            SPEC_KEY: {"schema": RECORD_SCHEMA, "slug": plan["slug"], "record": "%s/%s" % (plan["folder"], RECORD_NAME),
                       "manifest_sha256": plan["manifest_sha256"],
                       "surfaces": [{"key": s["key"], "title": s["title"]} for s in plan["surfaces"]],
                       "evidence": [{"path": e["path"], "words": e["words"]} for e in plan["evidence"]],
                       "files": pins},
        })
        output.spec_sheet = spec
        output.save()

    views = []
    for page in range(1, len(plan["pages"]) + 1):
        made = [drawing_views.picture(task, page, width, None, output=output)
                for width in (drawing_views.THUMB_PX, drawing_views.MAIN_PX)]
        views.append({"page": page, "made": all(made)})
    record = {"schema": RECORD_SCHEMA, "slug": plan["slug"], "task_id": task.pk, "output_id": output.pk,
              "target": plan["target"], "product": plan["product"], "manifest_sha256": plan["manifest_sha256"],
              "files": pins, "published_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()}
    data = (json.dumps(record, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    _write(record_path(plan["slug"]), data, hashlib.sha256(data).hexdigest())
    return {"task_id": task.pk, "output_id": output.pk, "created": created, "url": "/dashboard/designs/%d/" % task.pk,
            "record": str(record_path(plan["slug"])), "views": views, "written": written}


def checked(slug: str) -> dict:
    """The record beside the copies, with every pinned copy re-hashed; raises ``Changed`` naming the first that is gone
    or no longer the bytes published. This audits the adjacent publication record; the files door separately checks
    each download against the current output's database pins and serves the exact verified byte snapshot (D-D14-4)."""
    path = record_path(slug)
    if not path.is_file():
        raise Changed("%s has no record: it was never published here" % slug)
    record = json.loads(path.read_text(encoding="utf-8"))
    root = Path(settings.MEDIA_ROOT).resolve()
    for rel, pin in record["files"].items():
        copy = (root / rel).resolve()
        if not copy.is_relative_to(root):
            raise Changed("%s points outside MEDIA_ROOT" % rel)
        if not copy.is_file():
            raise Changed("%s is gone since it was published" % rel)
        if _sha(copy) != pin["sha256"]:
            raise Changed("%s changed since it was published" % rel)
    return record
