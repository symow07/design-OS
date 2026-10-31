import functools
import os
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from apps.core.models import Brand, Product
from apps.dashboard.words import STATUS_WORDS
from apps.pipeline.models import DesignTask
from apps.pipeline.spend_estimates import measured_costs


def _active_brand(request, brands):
    """Resolve the dashboard's active brand (Milestone 11.2 / audit H3).

    ?brand=<id> switches and is remembered in the session; otherwise the
    session choice wins; otherwise the first brand by id (deterministic —
    never an unordered .first()).
    """
    requested = request.GET.get("brand")
    if requested:
        brand = next((b for b in brands if str(b.id) == str(requested)), None)
        if brand:
            request.session["brand_id"] = brand.id
            return brand
    stored = request.session.get("brand_id")
    brand = next((b for b in brands if b.id == stored), None)
    if brand:
        return brand
    return brands[0] if brands else None


# [the owner's answer to the UI directions of 2026-09-25: the single-page dashboard that stood here as the home — the
# queue, the product picker and the brand panel, the rest driven by the DRF API — is served now only where a design is
# started or opened (`new_design`, `design`); the home is the board, below.]


def _start_from(request):
    """§BH55 Phase 3: "Start a new design from this one" in the Library opens Start a design filled in with a finished
    design's brief, what it is and its product — the cost under the button, the create door's checks run on the
    click — where the Library spent on one click, made a packaging task whatever the design was, and ran none of
    those checks. Only a finished design fills it in; its brand becomes the active one, so its product is offered."""
    raw = request.GET.get("from") or ""
    if not raw.isdigit():
        return None
    from apps.pipeline.models import PackagingOutput
    output = PackagingOutput.objects.select_related("task").filter(pk=int(raw), is_final_approved=True).first()
    if output is None:
        return None
    task = output.task
    if task.brand_id:
        request.session["brand_id"] = task.brand_id
    lines = (task.task_text or "").strip().splitlines()
    return {"task_text": task.task_text, "design_target": task.design_target, "product_id": task.product_id,
            "title": (lines[0].strip() if lines else "")[:80]}


# [the owner's answer to the UI directions of 2026-09-25: a design's own address (§BH55 Phase 3) opens C's design page —
# `design`, at the end of this module — no longer the single-page dashboard opened on it]


#: each target's picture in the shell's one sprite (templates/_icons.html); the card's own "icon" names what it is
TARGET_SVG = {"bottle": "i-bottle", "forms": "i-forms", "carton": "i-box", "palette": "i-palette", "stack": "i-both", "gift": "i-gift",
              "stand": "i-stand", "leaflet": "i-doc", "booth": "i-booth", "social": "i-phone"}


def _with_sizes(products):
    from apps.dashboard.products import size_words
    rows = list(products)
    for p in rows:
        p.size_words = size_words(p)
    return rows


def _costs_in_words(costs: dict, cards: list) -> dict:
    names = {c["value"]: c["name"] for c in cards}
    return {**costs, "start_design": [dict(s, target_words=names.get(s["target"], s["target"]))
                                      for s in costs.get("start_design") or []]}


def _inspiration_offer() -> dict:
    """§BH69(2): what the start page's inspiration box says before anything is dropped — the most pictures a design
    takes, and what reading one costs, measured on the ledger once there are reads (a cent or so before)."""
    from apps.pipeline.services import inspiration
    step = (measured_costs().get("steps") or {}).get("inspiration_read") or {}
    if step.get("rows"):
        cost = "about $%.3f a picture, measured over %d read%s" % (step["usd"], step["rows"], "" if step["rows"] == 1 else "s")
    else:
        cost = "about a cent a picture"
    return {"max": inspiration.MAX_PICTURES, "cost_words": cost, "kind": inspiration.KIND}


def _sticker_offer() -> dict:
    """[His final goal, 2026-10-05, B3] what the start page's sticker box says: the most pictures, what a read costs."""
    from apps.ire.back_info import KIND
    from apps.pipeline.services import inspiration
    step = (measured_costs().get("steps") or {}).get("sticker_read") or {}
    if step.get("rows"):
        cost = "about $%.3f a picture, measured over %d read%s" % (step["usd"], step["rows"], "" if step["rows"] == 1 else "s")
    else:
        cost = "about a cent a picture"
    return {"max": inspiration.MAX_PICTURES, "cost_words": cost, "kind": KIND}


def _inside_offer() -> dict:
    """[His final goal, 2026-10-05, B1: "An "Inside reference" picture slot beside the inspiration box (one or more
    pictures)."] What the start page's inside box says: the most pictures, what a read costs, measured once there are
    reads."""
    from apps.ire.inside_print import KIND, OPERATION
    from apps.pipeline.services import inspiration
    step = (measured_costs().get("steps") or {}).get(OPERATION) or {}
    if step.get("rows"):
        cost = "about $%.3f a picture, measured over %d read%s" % (step["usd"], step["rows"], "" if step["rows"] == 1 else "s")
    else:
        cost = "about a cent a picture"
    return {"max": inspiration.MAX_PICTURES, "cost_words": cost, "kind": KIND}


def _start_context(request, start_from=None) -> dict:
    """What the start page asks with: the targets (data, not markup — the template and the tests read the same list),
    the active brand's products with their sizes, the reference limits, and what starting costs, measured."""
    from apps.pipeline.services.revision import current_revision
    from apps.pipeline.targets import ui as target_ui
    brands = list(Brand.objects.order_by("id"))
    brand = _active_brand(request, brands)
    products = Product.objects.order_by("product_id")
    if brand:
        products = products.filter(brand=brand)
    # a start filled in from a finished design chooses its target; [his last goal before the pitch, 2026-10-16, Step 1
    # (5): "New design: nothing pre-selected"] any other start chooses none — Start asks for one (poll.js submitTask)
    default = (start_from["design_target"]
               if start_from and start_from["design_target"] in target_ui.ACTIVE_TARGETS else "")
    cards = [{**c, "svg": TARGET_SVG.get(c["icon"], "i-spark")} for c in target_ui.TARGET_CARDS]
    return {
        "target_cards": cards,
        "default_target": default,
        "default_target_name": next((c["name"] for c in cards if c["value"] == default), ""),
        "start_from": start_from,
        # Find's "Start a new design: …" opens the four questions with the words already in (never a finished design's)
        "brief": "" if start_from else (request.GET.get("brief") or "").strip()[:600],
        "selector_explanation": target_ui.SELECTOR_EXPLANATION,
        "container_hint_fields": target_ui.CONTAINER_HINT_FIELDS,
        # §BH70(1), item 15: which targets show them — the page reads this, never its own copy
        "hint_targets": target_ui.HINT_TARGETS,
        "profile_gate_note": target_ui.PROFILE_GATE_NOTE,
        # B4b-2 §8: the browser reads the limit and allowlist from here. It must never carry its own copy of either.
        "reference_config": target_ui.reference_config(),
        # the product container's reference zones — all but "inspiration", whose place the inspiration box takes
        "reference_categories": target_ui.START_REFERENCE_CATEGORIES,
        # §BH69(2): the inspiration box, for every kind of design — how many pictures, and what a read costs
        "inspiration": _inspiration_offer(),
        # [his final goal, 2026-10-05, B1] the inside box beside it, for a carton's inside print
        "inside": _inside_offer(),
        "sticker": _sticker_offer(),                        # [his final goal, B3] the custom sticker's picture
        "reference_only_notice": target_ui.REFERENCE_ONLY_NOTICE,
        "brand": brand, "brands": brands,                   # the brand switch (the checklist of 2026-09-26)
        "products": _with_sizes(products),                  # §BH55 Phase 3: each size in the menu
        "status_words": STATUS_WORDS,
        # §BH54(k) 1: what starting a design costs, measured, beside the button that spends it — each target by the
        # name its card carries, never its key ("product_container")
        "spend_costs": _costs_in_words(measured_costs(), cards),
        # the values the start form's scripts read, handed over as data — the page carries no inline script
        "page": {"task_id": None, "brand_id": brand.pk if brand else None,
                 "current_user": request.user.get_username(), "build": current_revision()},
    }



#: how many of each the Library's page shows before its "all ›"
LIBRARY_SAMPLE = 8
FINISHED_PAGE = 24
#: the kinds of text the Library's page shows the face of first (every kind is on the brand's page)
LIBRARY_ROLES = ("display", "heading", "body", "arabic-display")
#: a finished design's files, in the words a designer reads (the record's own fields stay the record's)
FILE_WORDS = (("design_preview_ai", "The design (.ai, editable)"), ("design_preview", "The design (picture)"),
              ("production_pdf", "Print PDF"), ("dieline_ai_file", "Dieline (.ai)"), ("dieline_file", "Dieline (SVG)"),
              ("spec_pdf", "Spec sheet (PDF)"))


def artworks(rows) -> list[dict]:
    """Each artwork once, however many files it is on — C's Library ("each artwork is shown once, though it is on file as
    AI and JPG"): the rows of one folder with one name, whatever its kind of file, are one artwork, shown by its first
    file that is drawn here and said with the kinds it is on ("AI + JPG"). A file's own tier, grant and credit stay on
    the materials page, file by file."""
    by, out = {}, []
    for m in rows:
        stem, dot, kind = m["name"].rpartition(".")
        key = (m["folder"], (stem if dot else m["name"]).lower())
        art = by.get(key)
        if art is None:
            art = by[key] = dict(m, kinds=[])
            out.append(art)
        elif m.get("drawable") and not art.get("drawable"):
            art.update(n=m["n"], sha=m["sha"], drawable=True)
        if dot and kind.upper() not in art["kinds"]:
            art["kinds"].append(kind.upper())
    return out


def families(faces) -> list[dict]:
    """The granted faces by family, as C's Library shows them — one card each, drawn in its regular style where it has
    one, with how many styles it has and the kinds of text it is first chosen for."""
    import re
    out, by = [], {}
    for f in faces:
        fam = by.get(f["family"])
        if fam is None:
            fam = by[f["family"]] = {"family": f["family"], "scripts": f["scripts"], "stem": f["stem"], "styles": [],
                                     "serves": []}
            out.append(fam)
        style = f["postscript"].partition("-")[2] or "Regular"
        fam["styles"].append(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", style))
        if style == "Regular":
            fam["stem"] = f["stem"]
        fam["serves"] += [w for w in f.get("serves") or [] if "(choice" not in w and w not in fam["serves"]]
    return out


def _can_see_finished(user) -> bool:
    """Finished designs are seen by a member of the team — the API's own boundary (IsTeamMember: any role at all)."""
    from apps.pipeline.permissions import ALL_ROLES, user_has_role
    return user_has_role(user, *ALL_ROLES)


def _finished_rows(params=None):
    """The finished designs (a final-approved output), newest first, found as the Library's API found them (that API
    left in the clean-up of 2026-10-04; its filters stay in library_views) — by words,
    brand, product category and date — with who approved each and what it spent."""
    from django.db.models import OuterRef, Subquery, Sum

    from apps.pipeline.library_views import _apply_filters
    from apps.pipeline.models import GateDecision, PackagingOutput
    approver = Subquery(GateDecision.objects.filter(task=OuterRef("task_id"), gate="gate_2", decision="approve")
                        .order_by("-decided_at").values("decided_by__username")[:1])
    qs = (PackagingOutput.objects.filter(is_final_approved=True)
          .select_related("task", "task__brand", "task__product", "approved_image")
          .annotate(_approver_name=approver, _task_cost=Sum("task__api_calls__cost_usd")).order_by("-created_at"))
    return _apply_filters(qs, params or {})


def _finished_card(output) -> dict:
    """A finished design as the Library shows it: its own picture (the design, before the concept it was made from),
    its name, what it is, its product, when it was finished and by whose approval, and its files named in words."""
    from apps.dashboard import board
    from apps.pipeline.library_views import _picture
    picture, picture_is = _picture(output)
    task = output.task
    return {
        # [his last goal before the pitch, 2026-10-16, Step 1 (3): "Design titles = the product name"] as every
        # screen names it (board.title_of) — it read the brief's first line
        "id": output.pk, "task_id": task.pk, "title": board.title_of(task, output.spec_sheet or {}),
        "target": task.get_design_target_display(),
        "picture": picture.url if picture else None, "picture_is": picture_is,
        "product": task.product.name if task.product_id else "", "brand": task.brand.name if task.brand_id else "",
        "finished": output.created_at, "approver": getattr(output, "_approver_name", None),
        "files": [(words, getattr(output, field).url) for field, words in FILE_WORDS if getattr(output, field)],
        "url": reverse("dashboard:finished_design", args=[output.pk]),
        "design_url": reverse("dashboard:design", args=[task.pk]),
        "start_url": reverse("dashboard:new_classic") + f"?from={output.pk}",
    }


def _made_rounds(user, params=None) -> list:
    """The Library's finished designs since the owner's goal of 2026-10-29: the rounds whose files are made (Make my
    files wrote their files.zip), newest first, found by the words of their brief and the day they were made — each as
    the finished card draws it (templates/dashboard/library/_finished_card.html). The old approved outputs keep their
    own pages (finished_design), unlisted."""
    import json
    from datetime import date
    params = params or {}
    words = (params.get("q") or "").lower()
    days = []
    for key in ("date_from", "date_to"):
        try:
            days.append(date.fromisoformat(params.get(key) or ""))
        except ValueError:
            days.append(None)                         # a date the record cannot hold is left out, never a fault
    made = []
    for record in your_rounds(user):
        card = round_card(record)
        if card["state"] != "finished":
            continue
        if words and words not in json.dumps(record.product_brief, ensure_ascii=False).lower():
            continue
        day = card["finished"].date()
        if (days[0] and day < days[0]) or (days[1] and day > days[1]):
            continue
        files = [("All the files (zip)", card["made"])]
        report = (record.master_build.publication or {}).get("report")
        if report:
            files.append(("What was made (README)",
                          reverse("dashboard:product_round_files_download", args=[record.pk, report])))
        made.append({"id": record.pk, "title": card["title"], "target": card["what"], "product": "", "approver": "",
                     "picture": card["picture"], "picture_is": "design", "finished": card["finished"], "files": files,
                     "url": card["files_url"]})
    return made


@login_required
@require_GET
def library(request):
    """THE LIBRARY — C's (his pick of the executor's options, a691f56: "starting a design, the library and history are
    C's"): everything a design is made from, on one page — the brand's colours, the faces its type is set in and its
    mark; the materials that can be placed, each artwork once; the granted faces; the products and their sizes; and the
    finished designs with their files — each section a click from its whole page. Read-only; the same library opens
    beside every design while it is worked on (templates/dashboard/_library_panel.html)."""
    from datetime import date

    from apps.dashboard import brand_library as bl
    from apps.dashboard import materials_library as ml
    from apps.dashboard import products as pr
    from apps.ire import brand_mark
    brands = list(Brand.objects.order_by("id"))
    brand = _active_brand(request, brands)
    mark = brand_mark.approved_master()
    try:
        mark_date = date.fromisoformat(str((mark.get("approval") or {}).get("date") or ""))
    except ValueError:
        mark_date = None
    found = ml.search(tier="placeable")
    arts = artworks(found.get("rows") or [])
    faces = [f for f in bl.faces() if f["granted"]]
    stems = {f["stem"]: f for f in faces}
    roles = [dict(r, family=stems[r["face"]]["family"]) for r in bl.type_roles()
             if r["role"] in LIBRARY_ROLES and r.get("face") in stems]
    see = _can_see_finished(request.user)
    finished = _made_rounds(request.user) if see else []
    listed = pr.listing(brand)
    products, tests = [r for r in listed if not r["test"]], [r for r in listed if r["test"]]
    return render(request, "dashboard/library/overview.html", {
        "section": "all", "brand": brand, "brands": brands, "colour_systems": bl.colour_systems(brand),
        "mark_approved": mark.get("state") == brand_mark.APPROVED, "mark_date": mark_date,
        "roles": roles, "families": families(faces), "face_count": len(faces),
        "record": found.get("record"), "counts": found.get("counts") or {},
        "counts_words": {k: f"{v:,}" for k, v in (found.get("counts") or {}).items()},
        "artworks": [a for a in arts if a.get("drawable")][:LIBRARY_SAMPLE], "artwork_count": len(arts),
        "products": products[:LIBRARY_SAMPLE], "product_count": len(products), "tests": tests,
        "can_see_finished": see, "finished": finished[:4], "finished_count": len(finished),
    })


@login_required
@require_GET
def finished_designs(request):
    """FINISHED DESIGNS — part of the Library (C's: "one library, with finished designs part of it"): since the owner's
    goal of 2026-10-29 every round whose files are made, with its picture and its files, found by words or by the day
    it was made; each opens its faces and files. The old approved outputs keep their own pages, unlisted (their brand and
    category filters went with them). It was a page of its own, outside the one shell, that drew its cards with a
    script."""
    from urllib.parse import urlencode
    see = _can_see_finished(request.user)
    params = {k: (request.GET.get(k) or "").strip()[:100] for k in ("q", "date_from", "date_to")}
    rows = _made_rounds(request.user, params) if see else []
    count = len(rows)
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except ValueError:
        page = 1
    pages = max(1, -(-count // FINISHED_PAGE))
    page = min(page, pages)
    shown = rows[(page - 1) * FINISHED_PAGE:page * FINISHED_PAGE]
    return render(request, "dashboard/library/finished.html", {
        "section": "finished", "can_see_finished": see, "finished": shown, "count": count, "params": params,
        "page": page, "pages": pages, "query": urlencode([(k, v) for k, v in params.items() if v]),
        "more_open": any(params[k] for k in ("date_from", "date_to")),
    }, status=200 if see else 403)


@login_required
@require_GET
def finished_design(request, output_id):
    """ONE FINISHED DESIGN, at its own address: its picture, what it is, its product and brand, the size it was made at,
    the direction chosen and what it spent; its files named in words; the way back to the design itself; a new design
    started from it — Start a design filled in, the cost under its button, never a click that spends; what was asked,
    and each approval in words."""
    from datetime import datetime

    from apps.pipeline.library_views import _approvals, _size_words
    if not _can_see_finished(request.user):
        return render(request, "dashboard/library/finished.html", {"section": "finished", "can_see_finished": False},
                      status=403)
    output = get_object_or_404(_finished_rows(), pk=output_id)
    card = _finished_card(output)
    approvals = [dict(a, at=datetime.fromisoformat(a["at"]) if a["at"] else None) for a in _approvals(output.task)]
    return render(request, "dashboard/library/finished_design.html", {
        "section": "finished", "f": card, "size": _size_words(output.spec_sheet or {}),
        "direction": output.approved_image.direction_name if output.approved_image_id else "",
        "spent": float(getattr(output, "_task_cost", None) or 0), "asked": output.task.task_text,
        "approvals": approvals,
    })


@login_required
@require_GET
def brand_library(request):
    """§BH55 Phase 3: THE BRAND'S OWN LIBRARY — its colours and the part each plays, its type and its faces, its mark,
    and what a design is told about it, read from the records that govern them (apps/dashboard/brand_library.py).
    Read-only; the active brand's."""
    from apps.dashboard import brand_library as bl
    brands = list(Brand.objects.order_by("id"))
    brand = _active_brand(request, brands)
    return render(request, "dashboard/library/brand.html", {
        "section": "brand", "brand": brand, "brands": brands, "colour_systems": bl.colour_systems(brand),
        "colour_roles": bl.colour_roles(), "type_roles": bl.type_roles(), "exempt_surfaces": bl.exempt_surfaces(),
        "faces": bl.faces(), "pool_faces": bl.pool_count(), "marks": bl.marks(), "knowledge": bl.brand_knowledge(brand),
    })


@login_required
@require_GET
def face_specimen(request, stem):
    """§BH55 Phase 3: a governed face's specimen, drawn on the server — the font file itself is never linked. Whole, or
    short — ?show=name (a product's name, set large) or ?show=glyph (two letters); any other value, whole."""
    from apps.dashboard import brand_library as bl
    show = request.GET.get("show") or ""
    png = bl.specimen_png(stem, show if show in bl.SPECIMEN_SHOWS else "whole")
    if png is None:
        raise Http404("not a governed face")
    response = HttpResponse(png, content_type="image/png")
    # [his last goal before the pitch, 2026-10-16, Step 1 (7): "every font specimen shows its sample (Poppins is
    # blank)"] each specimen is asked for as its page opens, never lazily — a lazy picture in a scrolled or hidden panel
    # can stay unasked (eighteen Poppins styles among 85) — and kept by the browser for the day, so a page of them is
    # drawn at once the next time
    response["Cache-Control"] = "private, max-age=86400"
    return response


@login_required
@require_GET
def brand_mark(request):
    """§BH55 Phase 3: the brand's mark in the product ink on the brand's cream — never the guideline's cyan."""
    from apps.dashboard import brand_library as bl
    png = bl.mark_png()
    if png is None:
        raise Http404("the mark's record refuses, or holds no picture")
    return HttpResponse(png, content_type="image/png")


@login_required
@require_GET
def house_references(request):
    """§BH55 Phase 3: past production designs from the production library (their lineage as the house's own not
    confirmed), as their rows describe them — never pictured: their files lie in a reference folder, and reference
    bytes are never served (§BH53(b), §BH54(b))."""
    from apps.core.models import DesignReference
    from apps.dashboard import brand_library as bl
    q = (request.GET.get("q") or "").strip()[:100]
    return render(request, "dashboard/library/references.html", {
        "section": "references", "q": q, "references": bl.references(q),
        "total": DesignReference.objects.filter(active=True).count(),
    })


@login_required
@require_GET
def materials_library(request):
    """Day 7 §5: THE LIBRARY — every unique file of the materials library from its index (docs/audit/day-7/library/
    materials-index.json: what each file shows, its tags and measured colours, the surfaces it suits, its rights tier under
    D-D7-1), by kind with counts, pictured through its Day 7 preview; searchable by words and colour; filtered by rights tier
    and surface; the excluded fonts listed under their own heading. Read-only (apps/dashboard/materials_library.py)."""
    from urllib.parse import urlencode

    from apps.dashboard import materials_library as ml
    kind = (request.GET.get("kind") or "").strip()[:20]
    tier = (request.GET.get("tier") or "").strip()[:10]
    if tier not in ("", "house", "GRANTED", "excluded"):
        tier = ""
    surface = (request.GET.get("surface") or "").strip()[:20]
    if surface and surface not in ml.SURFACE_WORDS:
        surface = ""
    q = (request.GET.get("q") or "").strip()[:100]
    colour = (request.GET.get("colour") or "").strip()[:7]
    if not ml.index_present():
        return render(request, "dashboard/library/materials.html", {"section": "materials", "record": False, "found": {"rows": [], "n": 0}, "counts": {},
                                                                     "shown": [], "page": 1, "pages": 1, "query": "", "kind": "", "tier": "", "surface": "", "q": "", "colour": ""})
    counts = ml.index_counts()
    found = ml.search_index(kind=kind, tier=tier, surface=surface, q=q, colour=colour)
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except ValueError:
        page = 1
    pages = max(1, -(-len(found["rows"]) // ml.PAGE_SIZE))
    page = min(page, pages)
    return render(request, "dashboard/library/materials.html", {
        "section": "materials", "record": True, "found": found, "counts": counts, "kind": kind, "tier": tier, "surface": surface, "q": q, "colour": colour,
        "surfaces": sorted(ml.SURFACE_WORDS.items(), key=lambda kv: kv[1]), "excluded_heading": ml.EXCLUDED_HEADING,
        "excluded_count": counts["tiers"].get("excluded", 0), "granted_count": counts["tiers"].get("GRANTED", 0),
        "shown": found["rows"][(page - 1) * ml.PAGE_SIZE:page * ml.PAGE_SIZE], "page": page, "pages": pages,
        "query": urlencode([(k, v) for k, v in (("kind", kind), ("tier", tier), ("surface", surface), ("q", q), ("colour", colour)) if v]),
        "colour_bad": bool(colour) and found.get("colour") is None,
    })


@login_required
@require_GET
def material_detail(request, sha):
    """Day 7 §5: one indexed file — its metadata, measured colours, rights under D-D7-1, its tier record where one exists,
    and where it has been used (the concept references that pinned its hash)."""
    from apps.dashboard import materials_library as ml
    from apps.pipeline.models import ConceptReference
    row = ml.detail(sha)
    if row is None:
        raise Http404("not an indexed material")
    used = [{"task_id": r.task_id, "words": (getattr(r.task, "task_text", "") or "")[:90], "permission": r.permission_status,
             "created": r.created_at, "role": (r.description or "").split(" · ", 1)[0]}
            for r in ConceptReference.objects.filter(library_item_id="materials:" + sha).select_related("task").order_by("-created_at")[:50]]
    return render(request, "dashboard/library/material_detail.html", {"section": "materials", "row": row, "card": row["card"], "used": used,
                                                                       "excluded_heading": ml.EXCLUDED_HEADING})


@login_required
@require_GET
def material_preview(request, sha):
    """Day 7 §5: the Day 7 preview of an indexed file (a hash-named PNG) — never the file itself."""
    from django.http import FileResponse
    from apps.dashboard import materials_library as ml
    path = ml.preview_file(sha)
    if path is None:
        raise Http404("no preview for this hash")
    return FileResponse(open(path, "rb"), content_type="image/png")


@login_required
@require_GET
def status_page(request):
    """STATUS — B's Status in C's look (the owner's pick of 2026-09-25): what is working, what waits for him and what needs
    his attention, from the board's one classification, with the reason and one thing to do; spending against the caps;
    whether the system answers. Below it, the records §BH55 Phase 3 put here (slice 4 of §BH51), each read now from what
    governs it; the queue and the worker are probed only when a person asks (?probe=1)."""
    from apps.dashboard import board
    from apps.dashboard import status as st
    cards = board.classify()
    context = board_context(request, cards)
    view = context["cards_by_id"]
    counts = context["counts"]
    waiting_groups = []
    for c in cards:
        if c.state != board.WAITING:
            continue
        words = c.next_words.split(" — ")[0]
        group = next((g for g in waiting_groups if g["words"] == words), None)
        if group is None:
            group = {"words": words, "cards": []}
            waiting_groups.append(group)
        group["cards"].append(view[c.task_id])
    # §BH55 Phase 3 (survey row 4.22): a container that waits for a review it cannot pass says why, beside itself
    reviewing = [c.task_id for c in cards if c.state == board.WAITING and c.lane == "review"
                 and c.target == "product_container" and c.task_id in view]
    for task in DesignTask.objects.filter(pk__in=reviewing):
        view[task.pk]["blocked"] = st._cannot_pass(task)
    order = [key for key, _words in board.LANES]
    lane_of = {c.task_id: c.lane for c in cards}
    waiting_groups.sort(key=lambda g: order.index(lane_of.get(g["cards"][0]["task_id"], "describe")))
    spend = st.spending()
    spend_pct = min(100.0, round(100.0 * spend["last24"] / spend["cap_day"], 2)) if spend["cap_day"] else 0.0
    context.update({
        "summary": _status_summary(counts, spend),
        "tile_words": {
            "working": ("What the system is doing now." if counts[board.WORKING] else "Nothing is being worked on."),
            "waiting": ", ".join("%d %s" % (len(g["cards"]), g["words"].lower()) for g in waiting_groups) or
                       "Nothing waits for you.",
            "attention": "Each below, with its reason and one thing to do.",
        },
        "waiting_groups": waiting_groups,
        "working": [view[c.task_id] for c in cards if c.state == board.WORKING],
        "stuck": [view[c.task_id] for c in cards if c.state == board.STUCK],
        "spend_pct": max(spend_pct, 1.0) if spend["last24"] else 0.0,
        "waiting": st.waiting(), "targets": st.targets(), "gates": st.production_gates(), "spend": spend,
        "health": st.health(probe=request.GET.get("probe") == "1"), "drawing": st.DRAWING,
        "paid_settings": st.paid_settings(), "providers": st.providers(), "launch_checks": st.launch_checks(),
        "checks": st.record_gates(), "brain": st.brain(), "programme": st.programme(),
        "materials": st.materials_record(), "extent": st.suite_extent(),
    })
    return render(request, "dashboard/status.html", context)


def _status_summary(counts, spend) -> str:
    """The page's first sentence: every count in words, and the day's spend against its cap."""
    from apps.dashboard import board

    def n(count, one, many):
        return "%d %s" % (count, one if count == 1 else many)
    parts = [(n(counts[board.WORKING], "design is", "designs are") + " being worked on") if counts[board.WORKING]
             else "Nothing is being worked on",
             n(counts[board.WAITING], "design waits", "designs wait") + " for you",
             n(counts[board.ATTENTION], "needs", "need") + " your attention"]
    pct = (100.0 * spend["last24"] / spend["cap_day"]) if spend["cap_day"] else 0.0
    return "In plain words: %s, %s, and %s. The last 24 hours spent $%.2f — %s of the $%.0f daily cap." % (
        parts[0], parts[1], parts[2], spend["last24"], ("%.0f%%" % pct) if pct >= 1 else "under 1%", spend["cap_day"])


@login_required
@require_GET
def rulings_page(request):
    """§BH55 Phase 3: THE RULINGS — the owner's register and his review queue, newest first, searchable by words; beside
    each ruling what the brain measured, labelled as derived (apps/dashboard/rulings.py)."""
    from apps.dashboard import rulings as ru
    source = request.GET.get("source") or "register"
    if source not in ru.SOURCES:
        source = "register"
    q = (request.GET.get("q") or "").strip()[:120]
    found = ru.sections(source)
    brain = ru.brain_statuses() if source == "register" else {}
    measured = brain.get("by_id") or {}
    shown = [{**s, "status": ru.status_words(measured.get(s["id"])) if s["id"] else ""}
             for s in (ru.search(source, q) if q else list(reversed(found or [])))]
    return render(request, "dashboard/rulings.html", {
        "source": source, "title": ru.title_of(source), "sections": found, "shown": shown, "q": q, "brain": brain,
    })


@login_required
@require_GET
def ruling_detail(request, source, line):
    """§BH55 Phase 3: one section of the register or the queue, at its own address — its first line; both files are
    appended to and never rewritten above their end."""
    from apps.dashboard import rulings as ru
    if source not in ru.SOURCES:
        raise Http404("no such record")
    s = ru.text_of(source, line)
    if s is None:
        raise Http404("no section begins on that line")
    brain = ru.brain_statuses() if source == "register" else {}
    measured = (brain.get("by_id") or {}).get(s["id"]) if s["id"] else None
    return render(request, "dashboard/ruling.html", {
        "source": source, "title": ru.title_of(source), "s": s, "status": ru.status_words(measured), "brain": brain,
    })


@login_required
@require_GET
def products_library(request):
    """§BH55 Phase 3: THE PRODUCTS — each with what a design reads from it and what its size decides; a designer sets
    its size and what it is (apps/dashboard/products.py)."""
    return _products_page(request)


def _products_page(request, *, errors=(), status=200):
    from apps.dashboard import products as pr
    from apps.pipeline.permissions import ROLE_ADMIN, ROLE_DESIGNER, user_has_role
    brand = _active_brand(request, list(Brand.objects.order_by("id")))
    listing = pr.listing(brand)
    saved = next((f"{r['p'].name}: {r['size'] or 'no size on record — it will be estimated'}" for r in listing
                  if str(r["p"].pk) == request.GET.get("saved")), "")
    return render(request, "dashboard/library/products.html", {
        "section": "products", "brand": brand, "products": [r for r in listing if not r["test"]],
        "tests": [r for r in listing if r["test"]], "no_size": pr.NO_SIZE_WORDS,
        "can_edit": user_has_role(request.user, ROLE_DESIGNER, ROLE_ADMIN), "errors": list(errors),
        "saved": saved,
    }, status=status)


@login_required
@require_POST
def product_size(request, pk):
    """§BH55 Phase 3: a designer sets a product's size and what it is — all three measures, or none (none: a carton's
    size is then estimated, a paid step). Anything else is refused with its words, and nothing is half-saved."""
    from apps.dashboard import products as pr
    from apps.pipeline.permissions import ROLE_ADMIN, ROLE_DESIGNER, user_has_role
    if not user_has_role(request.user, ROLE_DESIGNER, ROLE_ADMIN):
        return HttpResponseForbidden("Setting a product's size is for a designer.")
    product = get_object_or_404(Product, pk=pk)
    if product.brand_id:
        request.session["brand_id"] = product.brand_id
    values, errors = pr.parse_size(request.POST)
    if errors:
        return _products_page(request, errors=errors, status=400)
    for field, value in values.items():
        setattr(product, field, value)
    product.product_type = (request.POST.get("product_type") or "").strip()[:100]
    product.save(update_fields=[*values, "product_type"])
    return redirect(f"{reverse('dashboard:products_library')}?saved={product.pk}#product-{product.pk}")


@login_required
@require_GET
def material_picture(request, n, sha):
    """§BH55 Phase 3: a placeable material's picture, drawn in memory — only for a PRODUCTION row whose file's own bytes
    carry no other tier (§BH54(b)); a reference is never pictured (§BH53(b))."""
    from apps.dashboard import materials_library as ml
    png = ml.picture_png(n, sha)
    if png is None:
        raise Http404("not a placeable material this machine can draw")
    return HttpResponse(png, content_type="image/png")


def _coerce_field_value(intent, field_name, raw):
    """Rule E: the submitted string becomes the type the field holds.

    The coercion itself lives in palette_governance so there is one
    enforcement point rather than a copy per caller.
    """
    from apps.pipeline.services import palette_governance as gov
    field = intent.get(field_name)
    try:
        return gov.coerce_to_type(
            None if field is None else field.value, raw)
    except gov.TypeCoercionError as exc:
        raise ValueError(f"{field_name!r}: {exc}") from None


@login_required
def palette_intent_confirmation(request, task_id=None):
    """PALT-M4C-4 §2 — the full confirmation flow.

    'WHAT THE ENGINE UNDERSTOOD FROM ES3083', with a schematic of the
    reading, per-field confidence and provenance, and owner actions that
    persist as a VERSIONED governed record beside a design_intent
    GateDecision.

    Server-rendered so the workflow works without JavaScript, matching the
    Gate-1 regeneration precedent. Without a task the page is a read-only
    preview: a confirmation is a governed act and needs something to be
    recorded against.
    """
    from apps.pipeline.models import DesignTask
    from apps.pipeline.services import palette_confirmation_flow as flow
    from apps.pipeline.services import palette_es3083_owner_confirmation \
        as owner_conf
    from apps.pipeline.services import palette_intent_confirmation as pc
    from apps.pipeline.services import palette_rect_tray_geometry as rt
    from apps.pipeline.services import palette_understanding_overlay as uo
    from apps.pipeline.services.palette_es3083_intent import (
        build_es3083_intent)

    task = get_object_or_404(DesignTask, pk=task_id) if task_id else None
    draft = build_es3083_intent()

    if request.method == "POST":
        if task is None:
            return HttpResponseBadRequest(
                "a confirmation must be recorded against a task")
        if not request.user.has_perm("pipeline.change_designtask"):
            return HttpResponseForbidden(
                "confirming a design reading is a governed act")
        if request.POST.get("reopen"):
            if task.status != flow.CONFIRMED:
                return HttpResponseBadRequest(
                    f"task is {task.status}; only a confirmed reading can "
                    "be reopened for revision")
            flow.open_confirmation(task, draft)
            return redirect("dashboard:palette_intent_confirmation_task",
                            task_id=task.pk, permanent=False)
        if task.status != flow.AWAITING:
            return HttpResponseBadRequest(
                f"task is {task.status}, not {flow.AWAITING}")
        # The record carries THIS submission's actions. Replaying the
        # canonical §1 record on every post would attribute a dozen
        # decisions the poster never made to the poster, and the audit
        # trail is the whole point of keeping draft and decision apart.
        record = (owner_conf.confirmation_record()
                  if request.POST.get("apply_es3083_baseline")
                  else pc.ConfirmationRecord(
                      concept_reference=draft.concept_reference,
                      draft_identity=draft.identity()))
        # per-field owner corrections from the panel
        for key, action in request.POST.items():
            if not key.startswith("action_") or not action:
                continue
            fname = key[len("action_"):]
            raw = request.POST.get(f"value_{fname}", "").strip()
            if action in (pc.CORRECT, pc.ADD) and not raw:
                return HttpResponseBadRequest(
                    f"{action} on {fname!r} needs a value; applying it "
                    "empty would erase the reading and record the loss as "
                    "an owner decision")
            try:
                value = _coerce_field_value(draft, fname, raw) \
                    if action in (pc.CORRECT, pc.ADD) else None
            except ValueError as exc:
                return HttpResponseBadRequest(str(exc))
            try:
                record.apply(pc.ConfirmationAction(route="PANEL_ACTION", 
                    field_name=fname, action=action, actor="OWNER",
                    new_value=value,
                    new_level=raw if action == pc.RECLASSIFY else "",
                    note="owner action from the confirmation panel"))
            except pc.ConfirmationError as exc:
                return HttpResponseBadRequest(str(exc))
        flow.save_confirmation(task, draft, record, user=request.user,
                               notes=request.POST.get("notes", ""))
        return redirect("dashboard:palette_intent_confirmation_task",
                        task_id=task.pk, permanent=False)

    tray = rt.build_rect_recessed_tray()
    confirmed = owner_conf.confirmed_intent()
    overlay_dir = os.path.join(settings.MEDIA_ROOT, "palette")
    os.makedirs(overlay_dir, exist_ok=True)
    overlay_path = os.path.join(overlay_dir, "es3083_understanding.png")
    uo.render_understanding(confirmed, tray, overlay_path)
    from apps.dashboard import words as w
    panel = pc.panel(draft)
    ctx = {
        "panel": panel,
        # [the owner's answer to the UI directions of 2026-09-25: the reading in words; what the form posts, unchanged]
        "rows": [w.intent_row_words(row) for row in panel["rows"]],
        "actions": [(a, w.INTENT_ACTION_WORDS.get(a, a.replace("_", " ").capitalize()))
                    for a in panel["available_actions"]],
        "levels": [(lv, w.INTENT_LEVEL_WORDS.get(lv, lv)) for lv in panel["available_levels"]],
        "status_words": w.status_words(task.status) if task else "",
        # "ConceptReference:6 ES3083… — BBROSE 'Outer Glow' eyeshadow palette (media/references/…png)": what it is
        "source_words": re.sub(r"\s*\([^)]*\)\s*$", "", str(panel["concept_reference"]).split(" — ", 1)[-1]),
        "annotations": uo.annotation_record(confirmed, tray),
        "overlay_url": f"{settings.MEDIA_URL}palette/"
                       "es3083_understanding.png",
        "task": task,
        "flow": flow.flow_state(task) if task else None,
        "current": flow.current_confirmation(task) if task else None,
        "history": flow.revision_history(task) if task else [],
        "can_confirm": bool(
            task and task.status == flow.AWAITING
            and request.user.has_perm("pipeline.change_designtask")),
        "can_revise": bool(
            task and task.status == flow.CONFIRMED
            and request.user.has_perm("pipeline.change_designtask")),
        "owner_scope": owner_conf.owner_confirmation(),
    }
    return render(request, "palette/intent_confirmation.html", ctx)


# ---------------------------------------------------------------------------------------------------------------------
# THE OWNER'S ANSWER TO THE UI DIRECTIONS OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "THE OWNER'S ANSWER
# TO THE UI DIRECTIONS"): "B's board, C's design page", "C's look" — "Build it." HOME IS THE BOARD: every design a card on
# the step it stands at, the "Needs attention" lane on top, the tests he folded away in one row at the foot. Every figure
# is the board's one classification (apps/dashboard/board.py); nothing here writes.

#: what a card's one link says, by the step it stands at — every card opens the design's own page
LANE_ACTION = {"describe": "Open it", "direction": "Choose one", "concept": "Choose a concept",
               "size": "Confirm the size", "review": "Review", "finished": "Files"}
LANE_EMPTY = {"describe": "Nothing is being set up.", "direction": "No directions wait for a choice.",
              "concept": "No concepts wait for a choice.", "size": "No size waits to be confirmed.",
              "review": "No design waits for review.", "finished": "No design is finished yet."}
STATE_ICON = {"working": "i-arc", "waiting": "i-clock", "attention": "i-alert", "stuck": "i-still",
              "finished": "i-check", "tried_again": "i-again", "folded": "i-fold"}
#: why each folded group is folded, in words
FOLD_WHY = {"planning test": "the system's own trial runs, kept out of your lists",
            "acceptance walkthrough": "the old acceptance walkthroughs — tests, not your work",
            "demo carton": "the demonstration carton — a test, not your work",
            "publication record": "records that publish a finished master read-only; nothing is meant to run"}


def _names_its_product(card) -> bool:
    """Whether a card's brief speaks of the product its record names — else the brief's first words go on the card,
    since one product record stands on briefs for other things (measured 2026-09-25: nine carton briefs on one)."""
    if not card.product_name:
        return True
    brief = card.brief_start.lower()
    return any(len(word) >= 4 and word.lower() in brief for word in card.product_name.split())


def _cost_words(card, costs) -> str:
    """What the card's next click spends, measured on the ledger (apps/pipeline/spend_estimates.py) — only where that
    click spends: choosing a direction draws three concepts; confirming a carton's size translates its label copy,
    where that is switched on — no picture is made for it (the clean-up of 2026-10-04, E3: it read "about $0.25–0.50",
    two image edits no carton makes any more)."""
    steps = (costs or {}).get("steps") or {}
    if card.state != "waiting":
        return ""
    if card.lane == "direction" and card.target != "palette":
        usd = (steps.get("choose_direction") or {}).get("usd")
        return "about $%.2f" % usd if usd else ""
    if card.lane == "size" and card.target == "packaging":
        usd = (steps.get("make_the_design") or {}).get("usd")
        return "about $%.2f" % usd if usd else ""
    return ""


def board_cards(cards, pictures, costs) -> list[dict]:
    """The page's view of each card: the classification's fields, its picture, its one link and what that click costs."""
    shown = []
    for c in cards:
        shown.append({
            "task_id": c.task_id, "url": c.url, "state": c.state, "lane": c.lane, "title": c.title, "what": c.what,
            "product_or_brief": c.product_name or c.title.rsplit(" — ", 1)[0],
            "brief_note": "" if _names_its_product(c) else c.brief_start,
            "next_words": c.next_words, "reason": c.reason, "last_sign": c.last_sign,
            "earlier_stops": c.earlier_stops, "later_try": c.later_try, "fold": c.fold,
            "picture": pictures.get(c.task_id), "icon": STATE_ICON.get(c.state, "i-clock"),
            "action": ("See why" if c.state in ("attention", "stuck") else
                       "Look again" if c.status == "container_stage_visually_rejected" else
                       "Watch it" if c.state == "working" else LANE_ACTION.get(c.lane, "Open it")),
            "cost": _cost_words(c, costs),
        })
    return shown


def board_context(request, cards=None) -> dict:
    """Everything the board and Status draw, from one classification."""
    from apps.dashboard import board
    cards = board.classify() if cards is None else cards
    product_id = int(request.GET["product"]) if (request.GET.get("product") or "").isdigit() else None
    shown_cards = [c for c in cards if product_id is None or _card_product(c) == product_id]
    grouped = board.board(shown_cards)
    pictures = board.pictures([c for c in shown_cards if c.state != board.FOLDED])
    costs = measured_costs()
    view = {c["task_id"]: c for c in board_cards(shown_cards, pictures, costs)}
    columns = [{"key": col["key"], "words": col["words"], "empty": LANE_EMPTY.get(col["key"], ""),
                "cards": [view[c.task_id] for c in col["cards"]]} for col in grouped["columns"]]
    folded = [{"key": g["key"], "words": g["words"], "why": FOLD_WHY.get(g["key"], ""),
               "cards": [view[c.task_id] for c in g["cards"]]} for g in grouped["folded"]]
    yours = [c for c in cards if c.state != board.FOLDED]
    products = Product.objects.filter(pk__in={_card_product(c) for c in yours} - {None}).order_by("name")
    return {"columns": columns, "attention": [view[c.task_id] for c in grouped["attention"]],
            "tried_again": [view[c.task_id] for c in grouped["tried_again"]], "folded": folded,
            "counts": board.counts(cards), "total_yours": len(yours), "products": products, "product_id": product_id,
            "fold_words": board.OWNER_FOLD_WORDS, "cards_by_id": view}


def _card_product(card):
    return getattr(card, "product_id", None)


# --- THE ROUNDS on Home, Designs and the Library (the owner's goal of 2026-10-29, §0: "Keep Home, Designs and Library,
# switched to the chain engines"): each reads the chain's Round records — what the round list and the top bar read — and
# no longer the old tasks' classification (board.classify), which only Status and Find still read.

#: Home's lanes for a round of the designer flow (PIPELINE.md's chain), left to right: (key, words, nothing-here words)
ROUND_LANES = (("ideas", "Research and boards", "No round is researching or waiting for its board."),
               ("designs", "Designs and your pick", "No round is drawing its designs or waiting for your pick."),
               ("files", "Faces and files", "No round is drawing its faces or waiting for your Accept."),
               ("finished", "Files made", "No round has made its files yet."))
#: what a round waiting for its owner asks, by its state
ROUND_WAITS = {"awaiting_board_pick": "Pick one mood board", "awaiting_pick": "Pick one design",
               "awaiting_marks": "Mark up to three inventions"}
#: the retired rounds, folded at the board's foot: (key, words, why)
ROUND_FOLD = ("retired", "Retired rounds", "they ran on the retired pipeline; their records stay in docs/rounds/")
ROUNDS_SHOWN = 100


def your_rounds(user) -> list:
    """This account's rounds, newest first (an admin's: every round) — the round list's own reading."""
    from apps.pipeline.models import Round
    records = Round.objects.select_related("master_build").order_by("-created_at", "-pk")
    if not (user.is_staff or user.is_superuser):
        records = records.filter(created_by=user)
    return list(records[:ROUNDS_SHOWN])


def _round_picture(record):
    """The picked design's picture, else the picked board's — served through the round's own pinned files; none while
    neither is published, or when a pin no longer matches."""
    from apps.dashboard.product_round_views import board_publication, publication
    try:
        published = publication(record)
    except (OSError, ValueError, TypeError):
        published = {}
    candidates = published.get("candidates") or {}
    if isinstance(candidates, list):
        candidates = {row["id"]: row for row in candidates}
    picked = (record.pick or {}).get("id")
    relative = (candidates.get(picked) or {}).get("picture") if picked else None
    if not relative:
        boards = board_publication(record).get("candidates") or {}
        relative = (boards.get(((record.artifacts or {}).get("board_pick") or {}).get("id")) or {}).get("picture")
    return reverse("dashboard:product_round_file", args=[record.pk, relative]) if relative else None


def _round_files(card, record, build):
    """Where a round stands once its pick is recorded: its files build's own record (round_files_gate)."""
    from apps.pipeline.services import round_files_gate as gate
    if build is None:
        if gate.flat_pick(record):
            return dict(card, state="stuck", next_words="Its files wait for the flat die's next step", action="Open it")
        return dict(card, state="waiting", next_words="Build the files", action="Build the files")
    files = reverse("dashboard:product_round_files", args=[record.pk])
    card = dict(card, url=files, files_url=files)
    if build.inputs.get("schema") != gate.FILES_SCHEMA:
        return dict(card, state="stuck", next_words=gate.RETIRED, action="Open it")
    download = (build.publication or {}).get("download") if build.state == "complete" else None
    if download:
        return dict(card, lane="finished", state="finished", next_words="Files made", action="Open the files",
                    made=reverse("dashboard:product_round_files_download", args=[record.pk, download]),
                    finished=build.updated_at)
    if build.state in ("queued", "running"):
        return dict(card, state="working", next_words=gate.STEP_LABELS.get(build.current_step, "Making your files"),
                    action="Watch it")
    if build.state == "failed":
        return dict(card, state="attention", next_words="Open the files build",
                    reason="The files build stopped; its page says why.", action="See why")
    if not gate.is_gate(build):
        return dict(card, state="stuck", next_words=gate.RETIRED, action="Open it")
    if gate.ready(build):
        return dict(card, state="waiting", next_words="Make my files", action="Make my files")
    rows = list(gate.board(build).values())
    refused = [row for row in rows if row["state"] == "failed" and gate.out_of_credits(row.get("error"))]
    if refused:
        return dict(card, state="attention", next_words="Add OpenAI credits, then redraw",
                    reason="OpenAI has no credits left, so %d face%s could not be drawn (nothing was charged). Add "
                           "credits to the OpenAI account, then press Redraw on each." % (
                               len(refused), "s" * (len(refused) != 1)), action="See why")
    if any(row["state"] == "failed" for row in rows):
        return dict(card, state="attention", next_words="Redraw the face that could not be drawn",
                    reason="A face could not be drawn this time; press Redraw on it.", action="See why")
    if any(row["state"] == "drawn" for row in rows):
        return dict(card, state="waiting", next_words="Accept or redraw each face", action="Accept the faces")
    return dict(card, state="working", next_words="Drawing your faces", action="Watch it")


def round_card(record) -> dict:
    """A round as Home, Designs, the Library and the top bar show it: where it stands (working on it, waiting for you,
    needs attention, can't move on here, finished) by its own record and its files build's, what happens next in
    words, the one place to go next and its picked design's picture. It reads rows and pinned files; it writes nothing."""
    from apps.pipeline.services import round_flow
    brief = record.product_brief or {}
    title = brief.get("name") or "Product round"
    kind = str(brief.get("product_type") or "").strip()
    page = reverse("dashboard:product_round", args=[record.pk])
    card = {"task_id": record.pk, "round_id": record.pk, "url": page, "page_url": page, "files_url": "",
            "title": title, "product_or_brief": title, "kind": kind,
            "what": (kind + " and its counter stand") if kind and brief.get("stand") else (kind or "A product round"),
            "brief_note": "", "reason": "", "earlier_stops": [], "later_try": None, "fold": "", "cost": "",
            "picture": None, "last_sign": record.updated_at, "created": record.created_at, "made": "", "finished": None}
    if round_flow.is_retired_round(record):
        card = dict(card, state="folded", lane=ROUND_FOLD[0], fold=ROUND_FOLD[0],
                    next_words=round_flow.retired_words(record), action="Open it")
    elif round_flow.rejected(record):
        card = dict(card, state="folded", lane=ROUND_FOLD[0], fold=ROUND_FOLD[0],
                    next_words=round_flow.rejected_words(record), action="Open it")
    elif record.state == "complete":
        try:
            card = _round_files(dict(card, lane="files", picture=_round_picture(record)), record,
                                getattr(record, "master_build", None))
        except (OSError, ValueError, KeyError, TypeError):
            # a round folder that cannot be read never stops Home or the top bar on every page: its own page says why
            card = dict(card, lane="files", state="stuck", next_words="Open the round to see where it stands",
                        action="Open it")
    else:
        card = dict(card, lane="ideas" if record.current_step in ("research", "boards", "board_pick") else "designs",
                    picture=_round_picture(record))
        if record.state in ("queued", "running"):
            card.update(state="working", action="Watch it",
                        next_words=round_flow.DESIGNER_STEP_LABELS.get(record.current_step, "Working on the round"))
        elif record.state in ROUND_WAITS:
            card.update(state="waiting", next_words=ROUND_WAITS[record.state], action=ROUND_WAITS[record.state])
        elif record.state == "failed":
            card.update(state="attention", next_words="Open the failed step", action="See why",
                        reason=record.error_message or "A step stopped; the round's page says why.")
        else:
            card.update(state="stuck", next_words="Open the round to see where it stands", action="Open it")
    return dict(card, icon=STATE_ICON.get(card["state"], "i-clock"))


def round_board_context(request) -> dict:
    """Everything Home draws, from the rounds' one classification (round_card): the Needs attention lane, the four
    lanes of the designer flow and the retired rounds folded at the foot — every round in exactly one."""
    cards = [round_card(r) for r in your_rounds(request.user)]
    kind = (request.GET.get("product") or "").strip()
    yours = [c for c in cards if c["state"] != "folded"]
    shown = [c for c in yours if not kind or c["kind"] == kind]
    retired = [c for c in cards if c["state"] == "folded"]
    columns = [{"key": key, "words": words, "empty": empty,
                "cards": [c for c in shown if c["lane"] == key and c["state"] != "attention"]}
               for key, words, empty in ROUND_LANES]
    folded = [{"key": ROUND_FOLD[0], "words": ROUND_FOLD[1], "why": ROUND_FOLD[2], "cards": retired}] if retired else []
    kinds = sorted({c["kind"] for c in yours if c["kind"]})
    counts = {state: sum(1 for c in yours if c["state"] == state)
              for state in ("working", "waiting", "attention", "stuck", "finished")}
    return {"columns": columns, "attention": [c for c in shown if c["state"] == "attention"], "tried_again": [],
            "folded": folded, "counts": counts, "total_yours": len(yours),
            "products": [{"pk": k, "name": k} for k in kinds], "product_id": kind or None, "fold_words": "",
            "cards_by_id": {c["round_id"]: c for c in cards}}


@login_required
@ensure_csrf_cookie
def index(request):
    """HOME — THE BOARD (his pick, 2026-09-25), on the rounds (the owner's goal of 2026-10-29: Home switched to the
    chain): every round a card on the step it stands at, read from round_card. An old address that carried a finished
    design to start from (?from=<output>, the Library's "Start a new design from this one") goes on to the classic start
    page, where that start lives; New design itself is the designer flow (2026-10-27)."""
    if request.GET.get("from"):
        return redirect("%s?from=%s" % (reverse("dashboard:new_classic"), request.GET["from"]))
    return render(request, "dashboard/home.html", round_board_context(request))


@login_required
@ensure_csrf_cookie
def new_design(request):
    """NEW DESIGN — C's start (his pick of the executor's options, a691f56: "starting a design, the library and history are C's"): four
    questions down one column and a rail keeping what is answered; every control is the start form's own, so what it
    sends is what it always sent, and nothing is spent until Start. A started design opens on its own page."""
    return render(request, "dashboard/new.html", _start_context(request, _start_from(request)))


FIND_LIMIT = 12


@login_required
@require_GET
def find(request):
    """FIND — what the one search box in the top bar finds (C's, 2026-09-25: "Find a design, a colour, a material — or
    start a new design"): designs by anything on their record, products by name or code, the brand's colours by name or
    colour, the granted faces by family, and materials that can be placed, by what they show — and a new design started
    with these words. Read-only; each section says how many it found and shows the first twelve."""
    from apps.dashboard import board, brand_library, history, materials_library
    from apps.pipeline.spend_estimates import measured_costs
    q = (request.GET.get("q") or "").strip()[:120]
    out = {"q": q, "designs": [], "products": [], "colours": [], "faces": [], "materials": [], "counts": {}}
    if q:
        words = q.lower()
        tasks = [r["task"] for r in history.task_list({"q": q})["rows"]]
        # [his last goal before the pitch, 2026-10-16, Step 1 (4)] Find finds an old design; only tests are left out
        cards = [c for c in board.classify(tasks, fold_old=False) if c.state != board.FOLDED] if tasks else []
        out["counts"]["designs"] = len(cards)
        shown = cards[:FIND_LIMIT]
        from apps.dashboard.history_views import TAG_CLASS
        out["designs"] = [dict(c, tag_class=TAG_CLASS.get(c["state"], "line"))
                          for c in board_cards(shown, board.pictures(shown), measured_costs())]
        brand = _active_brand(request, list(Brand.objects.order_by("id")))
        products = [p for p in _with_sizes(Product.objects.order_by("name"))
                    if words in (p.name or "").lower() or words in (p.product_id or "").lower()
                    or words in (p.name_ar or "")]
        out["counts"]["products"] = len(products)
        out["products"] = products[:FIND_LIMIT]
        colours = [dict(sw, system=cs["name"]) for cs in brand_library.colour_systems(brand) for sw in cs["swatches"]
                   if words in (sw["name"] or "").lower() or words in (sw["hex"] or "").lower()
                   or words in (sw["ink"] or "").lower() or words in (sw["role"] or "").lower()]
        out["counts"]["colours"] = len(colours)
        out["colours"] = colours[:FIND_LIMIT]
        faces = [f for f in brand_library.faces() if f["granted"] and words in (f["family"] or "").lower()]
        out["counts"]["faces"] = len(faces)
        out["faces"] = faces[:FIND_LIMIT]
        found = materials_library.search(tier="placeable", q=q)
        rows = [m for m in found.get("rows") or [] if m.get("drawable")]
        out["counts"]["materials"] = len(rows)
        out["materials"] = rows[:FIND_LIMIT]
    return render(request, "dashboard/find.html", out)


@login_required
@require_GET
def pulse(request):
    """The top bar's three counts as numbers, for static/js/shell.js to refresh while a page stays open (the owner's
    goal of 2026-09-25, (d): "What is running, what is waiting for me, and what failed are always visible."). Read from
    the board's one classification; writes nothing."""
    from apps.dashboard import board
    from apps.dashboard.context_processors import unread, round_activity
    tally = board.counts()
    rounds = round_activity(request.user)
    return JsonResponse({"counts": {"run": tally[board.WORKING]+len(rounds["run"]), "wait": tally[board.WAITING]+len(rounds["wait"]),
                                    "attn": tally[board.ATTENTION]+len(rounds["attn"])},
                         # the bell's number: this account's unread notifications (the checklist of 2026-09-26)
                         "unread": unread(request.user)})


@login_required
@require_GET
def brand_mark_svg(request):
    """The house mark in the top bar: the approved vector master on file (docs/brand/mark/, placed by the one guarded
    act on his words of 2026-09-25, "The ® circle trace looks right — approve it"), served as it is — the page inks it in
    Deep Rose through a CSS mask. With no approval on file it is not served, and the bar keeps its link."""
    from apps.ire import brand_mark
    found = brand_mark.approved_master()
    master = found.get("master")
    if master is None:
        raise Http404(found.get("reason") or "no approved mark on file")
    with open(master.path, "rb") as fh:
        data = fh.read()
    response = HttpResponse(data, content_type="image/svg+xml")
    response["Cache-Control"] = "private, max-age=3600"
    return response


# ---------------------------------------------------------------------------------------------------------------------
# A DESIGN'S OWN PAGE — C's design page (the owner's answer to the UI directions of 2026-09-25). What the page shows around
# the design's steps is read here from the rows: its name, where it stands, what it has spent against its cap, its
# concepts, what the library holds, and whether the design loop can try it. The steps themselves are drawn by the page's
# scripts from the design's live record, as they always were. Nothing here writes.

#: why the design loop cannot try a design, in words — the loop's own refusals, read (apps/dashboard/exploration_render.py)
ADJUST_REFUSAL_WORDS = {
    "EXPLORATION_RENDER_NEEDS_A_CONTAINER_TASK": (
        "Its artwork is drawn by the picture service, which costs money on every try — so it is not tried here; "
        "adjusting it that way needs your word first."),
    "EXPLORATION_RENDER_NEEDS_A_CONFIRMED_DROPPER_PROFILE": (
        "The design loop can redraw a dropper bottle, or a compact's lid, whose shape and size are confirmed; this one it "
        "cannot redraw yet."),
    "EXPLORATION_NEEDS_THE_CONCEPTS_READING": (
        "Its concept picture has not been read for drawing yet. That reading is a paid step, made when the design is "
        "drawn on the governed path, and the design loop never pays — so it cannot redraw this lid until then."),
    "EXPLORATION_FACE_FORM_REFUSED_BY_ITS_RECORD": (
        "Its record does not let this lid be drawn again as it stands, so the design loop cannot redraw it."),
    "EXPLORATION_RENDER_DRAWS_THE_M3_BACKBONE_ONLY": "This bottle is drawn a way the design loop cannot redraw.",
    "EXPLORATION_REFUSED_REFERENCE_ASSET": ("One of the pictures it is drawn from is a reference only — never placed — "
                                            "so it is not redrawn here."),
}
#: the steps at which a design has a drawing to adjust
ADJUSTABLE_STATUSES = ("awaiting_gate_2", "container_stage_visually_rejected")


def _refusal_words(text: str) -> str:
    code = str(text or "").split(":", 1)[0].strip()
    return ADJUST_REFUSAL_WORDS.get(code, "The design loop cannot redraw this design.")


def _design_direction(task) -> str:
    from apps.pipeline.models import CreativeBrief
    brief = CreativeBrief.objects.filter(task=task).only("directions", "selected_direction_id").first()
    if brief is None or not brief.selected_direction_id:
        return ""
    return next((str(d.get("name") or "") for d in (brief.directions or [])
                 if isinstance(d, dict) and d.get("direction_id") == brief.selected_direction_id), "")


def _design_concepts(task) -> list[dict]:
    from apps.dashboard import board
    shown = []
    for image in task.images.filter(superseded=False).exclude(image_file="").order_by("variation_number", "created_at"):
        url = board._picture_url(image.image_file.name)
        if url:
            # [his last goal before the pitch, 2026-10-16, Step 1 (6): "no empty concept thumbnails"] the rail shows a
            # small picture of each (``concept_thumb``) — each concept is a 2 MB picture, three a page, lazily asked for
            shown.append({"url": url, "chosen": image.is_approved, "direction": image.direction_name,
                          "thumb": reverse("dashboard:concept_thumb", args=[task.pk, image.pk])})
    return shown


#: the long side of a concept's small picture on a design's rail, in pixels (the rail draws it at most 210 wide, 2x)
THUMB_SIDE = 480


def _thumb_bytes(path: str, mtime: float) -> bytes:
    import io

    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((THUMB_SIDE, THUMB_SIDE))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=84)
    return buf.getvalue()


_thumb_cached = functools.lru_cache(maxsize=256)(_thumb_bytes)


@login_required
@require_GET
def concept_thumb(request, task_id, image_id):
    """[Step 1 (6)] a concept's small picture, made from its file in memory — never written anywhere — and only for a
    file the /files/ door itself would serve (``core.views.door_refusal``)."""
    from pathlib import Path

    from apps.core.views import door_refusal
    from apps.dashboard import board
    from apps.pipeline.models import GeneratedImage
    image = get_object_or_404(GeneratedImage, pk=image_id, task_id=task_id)
    if not board._picture_url(image.image_file.name):
        raise Http404("not a picture this page shows")
    root = Path(settings.MEDIA_ROOT).resolve()
    target = (root / image.image_file.name).resolve()
    refusal = door_refusal(target, root)
    if refusal is not None:
        return HttpResponseForbidden(refusal, content_type="text/plain; charset=utf-8")
    response = HttpResponse(_thumb_cached(str(target), target.stat().st_mtime), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=86400"
    return response


def _face_words(stem: str, faces: list) -> str:
    """A face by its family and its weight in words — "Amatic SC Bold" — never its file's stem."""
    family = next((f["family"] for f in faces if f["stem"] == stem), stem)
    weight = stem.split("-", 1)[1] if "-" in stem else ""
    weight = "".join(" " + ch if ch.isupper() and i else ch for i, ch in enumerate(weight)).strip()
    return ("%s %s" % (family, weight)).strip() if weight and weight.lower() not in family.lower() else family


def _refusal_sentence(why: str) -> str:
    """A loop refusal reads "CODE: REFUSED — sentence"; the page says the sentence, the code stays in the record."""
    return why.split(" — ", 1)[1] if " — " in why else why


def _lid_knobs(kinds: dict) -> tuple[list, list]:
    """The owner's pick on a lid's face: a colour for each element that shows one — from the brand's two systems — and a
    face for the name from the granted set; what cannot be tried is said, in words (exploration_render.knob_offer)."""
    knobs, notes = [], []
    for e in kinds["elements"]:
        label = e["words"][:1].upper() + e["words"][1:]
        if e["can_take_a_colour"]:
            knobs.append({"name": e["field"], "label": label, "kind": "colour", "hint": e["paints"],
                          "standing": e["standing"]["words"],
                          "options": [(p["hex"], p["words"]) for p in kinds["palette"]]})
        else:
            notes.append({"what": label, "why": e["why_not"]})
    for r in kinds["roles"]:
        label = "The face of " + r["words"]
        standing = r["standing"]
        others = [stem for stem in r["offer"] if stem != standing.get("stem")]
        if others:
            knobs.append({"name": r["field"], "label": label, "kind": "face",
                          "standing": _face_words(standing.get("stem") or "", kinds["faces"]),
                          "options": [(stem, _face_words(stem, kinds["faces"])) for stem in others]})
        else:
            notes.append({"what": label,
                          "why": "it stays in %s — no other granted face can set it" % _face_words(
                              standing.get("stem") or "", kinds["faces"]),
                          "record": [{"face": n["face"], "why": _refusal_sentence(n["why"])} for n in r["not_offered"]]})
    return knobs, notes


def _adjust_offer(request, task) -> dict:
    """Whether the design loop can try this design, and with which knobs — or why not, in words. On a lid's face the
    knobs are his pick: pick an element and try a colour or a face on it; on the dropper, its name."""
    from apps.dashboard import exploration_render, explorations
    shown = task.status in ADJUSTABLE_STATUSES
    offer = {"shown": shown, "available": False, "form": None, "reason": "", "knobs": [], "notes": [], "tries": 0,
             "loop_url": "/dashboard/history/tasks/%d/loop/" % task.pk}
    if not shown:
        return offer
    found = exploration_render.explorable(task)                       # what the design is decides first
    if not found.get("form"):
        offer["reason"] = _refusal_words(found.get("reason") or "EXPLORATION_RENDER_NEEDS_A_CONTAINER_TASK")
        return offer
    if explorations.owner_refusal(request.user):                      # §BH54(i): then whose account is looking
        offer["reason"] = "Trying designs is the owner's alone; this account cannot try this one."
        return offer
    kinds = exploration_render.knob_offer(task)
    if kinds.get("form") == "face":
        knobs, notes = _lid_knobs(kinds)
        offer.update(available=True, form="face", knobs=knobs, notes=notes, palette=kinds["palette"],
                     faces=[f for f in kinds["faces"] if "name" in f["roles"]])
    elif kinds.get("form") == "dropper":
        standing = exploration_render.standing_values(task)
        offer.update(available=True, form="dropper",
                     knobs=[{"name": "product_name", "label": "The name", "standing": standing.get("product_name")}])
    else:
        offer["reason"] = _refusal_words(kinds.get("refused") or "EXPLORATION_RENDER_NEEDS_A_CONTAINER_TASK")
        return offer
    offer["tries"] = sum(len(s.get("pictures") or []) for s in explorations.for_task(task.pk)
                         if s["slug"].startswith("t%d-loop-" % task.pk) and not s["refused"])
    return offer


def _library_offer(task, adjust) -> dict:
    """The library, beside the design: the brand's colours, the granted faces, materials that can be placed, and past
    designs of the same product — with what can be tried on THIS design said plainly."""
    from apps.dashboard import board
    from apps.dashboard import brand_library as bl
    from apps.dashboard import materials_library as ml
    found = ml.search(tier="placeable")
    past_tasks = [t for t in DesignTask.objects.select_related("product", "project")
                  .filter(product_id=task.product_id).exclude(pk=task.pk).order_by("-created_at")[:24]
                  if task.product_id and not board.fold_of(t)][:6]
    cards = board.classify(past_tasks) if past_tasks else []
    pictures = board.pictures(cards)
    lid = adjust.get("form") == "face"
    colours = bl.colour_systems(task.brand)
    if lid:                  # each swatch tried at the colour the loop's palette paints it in, by its system and name
        paints = {}
        for p in adjust.get("palette") or []:
            for system in [p["system"]] + list(p.get("also_in") or []):
                paints[(system, p["name"])] = p["hex"]
        for system in colours:
            for sw in system["swatches"]:
                sw["try_hex"] = paints.get((system["name"], sw["name"]))
    name_faces = {f["stem"] for f in adjust.get("faces") or []}
    return {
        "colours": colours,
        "faces": [dict(f, can_try=f["stem"] in name_faces) for f in bl.faces() if f["granted"]], "pool_faces": bl.pool_count(),
        "materials": [m for m in found.get("rows") or [] if m.get("drawable")][:6],
        "placeable": (found.get("counts") or {}).get("placeable", len(found.get("rows") or [])),
        "past": [{"url": c.url, "title": c.title, "picture": pictures.get(c.task_id)} for c in cards],
        "can_colour": lid, "can_face": lid and bool(name_faces),
        "colour_words": ("Your two colour systems, as their records hold them. "
                         + ("A metallic ink is tried at the flat colour the drawing paints it in." if lid else
                            "The design loop tries a colour on a compact's lid; this design's colours are here to "
                            "look at.")),
        "face_words": ("The faces granted for your designs, each drawn from its own file."
                       + (" Try one on the name — the Arabic name stays in the face that can set it." if lid else "")),
    }


# §BH69(2) — A DESIGN'S INSPIRATION PICTURES (the owner's goal of 2026-09-26): "Uploaded pictures are kept with the design
# so I can see them later", and a box "on a design's Adjust panel". What the box says a picture added there will do is
# read from where the design can still go: an artwork sent back at its review returns to its concepts
# (apps/pipeline/views.py _reject_artwork_to_gate_1), and new concepts drawn there take the words; a carton's or a
# bottle's concept stays chosen from its review on; a design rejected at its review goes no further.

def _inspiration_box_words(task) -> str:
    from apps.pipeline.targets.artwork import is_artwork_target
    if task.status != "awaiting_gate_2":
        return "This design goes no further as it is, so its words change nothing here — it is kept for you to see."
    if is_artwork_target(task.design_target):
        return "Its words go into new concepts if you ask for changes and then turn these concepts down for new ones."
    return ("Its concept is chosen, and nothing from here draws a new one — so its words change nothing in this design; "
            "it is kept for you to see.")


def _inspiration_kept(request, task, adjust) -> dict:
    """The design's inspiration pictures, each with what was taken from it — the picture itself to the accounts its file
    is served to (whoever started the design, and staff), its words to anyone — and, where the Adjust panel shows, the
    box that adds one, for a designer who may add to this design."""
    from apps.pipeline.models import CreativeBrief, InspirationReading
    from apps.pipeline.permissions import ROLE_ADMIN, ROLE_DESIGNER, user_has_role
    from apps.pipeline.services import inspiration
    user = request.user
    refs = list(task.references.filter(kind=inspiration.KIND).order_by("ordering", "id"))
    served = not task.created_by_id or task.created_by_id == user.id or user.is_staff or user.is_superuser
    readings = {r.sha256: r.reading
                for r in InspirationReading.objects.filter(sha256__in=[ref.sha256 for ref in refs if ref.sha256])}
    unread = ("Its read did not succeed, so its words were not used."
              if CreativeBrief.objects.filter(task=task).exists()
              else "Not read yet — it is read before this design's directions are planned.")
    rows = []
    for ref in refs:
        reading = readings.get(ref.sha256)
        taken = inspiration.taken(reading) if reading is not None else None
        rows.append({"name": ref.original_filename or "A picture", "taken": taken,
                     "seen": list(reading.get("seen_not_taken") or []) if reading is not None else [],
                     "unread": unread, "url": "/api/tasks/%d/references/%d/" % (task.pk, ref.pk) if served else ""})
    may_add = bool(adjust.get("shown")) and served and user_has_role(user, ROLE_DESIGNER, ROLE_ADMIN)
    return {"rows": rows, "can_add": may_add, "left": inspiration.MAX_PICTURES - len(refs),
            "cost_words": _inspiration_offer()["cost_words"], "box_words": _inspiration_box_words(task)}


@login_required
@require_GET
def design_adjust(request, task_id):
    """[his last goal before the pitch, 2026-10-16, Step 1 (6)] a design's Adjust panel and the library's tries — what
    its page leaves out so the drawing shows at once — rendered as the page would have rendered them."""
    from django.http import JsonResponse
    from django.template.loader import render_to_string
    task = get_object_or_404(DesignTask.objects.select_related("product", "project", "brand"), pk=task_id)
    adjust = _adjust_offer(request, task)
    ctx = {"task": task, "adjust": adjust, "lib": _library_offer(task, adjust),
           "inspiration": _inspiration_kept(request, task, adjust)}
    return JsonResponse({"adjust": render_to_string("dashboard/_adjust.html", ctx, request=request),
                         "library": render_to_string("dashboard/_library_panel.html", ctx, request=request)})


def _test_words(task) -> str:
    """The words a design marked as the executor's test carries beside its title ("Test one"), or "" — only where it is
    marked a test (``board.TEST_RUN_OPTION``) and was given words for it."""
    from apps.dashboard import board
    from apps.pipeline.services.master_tasks import TEST_WORDS_OPTION
    options = task.options if isinstance(task.options, dict) else {}
    words = options.get(TEST_WORDS_OPTION) if options.get(board.TEST_RUN_OPTION) else None
    return words if isinstance(words, str) else ""


@login_required
@ensure_csrf_cookie
def design(request, task_id):
    """A DESIGN'S OWN ADDRESS (§BH55 Phase 3), now C's design page. Its brand becomes the active one, as before."""
    from apps.dashboard import board
    from apps.pipeline.services.cost_ledger import task_cost_usd
    task = get_object_or_404(DesignTask.objects.select_related("product", "project", "brand"), pk=task_id)
    if task.brand_id:
        request.session["brand_id"] = task.brand_id
    card = board.classify([task], fold_old=False)[0]
    # [his last goal before the pitch, 2026-10-16, Step 1 (4)] a design folded away as a test is still shown, on its own
    # page, where it stands — never "Folded away"
    state = card.unfolded_state
    # [his last goal before the pitch, 2026-10-16, Step 1 (6): "The design page loads with the drawing visible fast (no
    # blank seconds ...)"] the Adjust panel's controls are worked out after the page shows (``design_adjust``): a
    # lid's knobs compose its face again, cold fonts and all — MEASURED on his database, 2026-10-16: design 141's page
    # took 20.9 s on a fresh process, 20.0 s of it here, and 131's 2.7 s
    adjust = {"shown": task.status in ADJUSTABLE_STATUSES, "pending": True, "available": False, "form": None,
              "knobs": [], "notes": [], "tries": 0}
    d = {"title": card.title, "name_ar": card.product_name_ar, "state": state,
         "state_words": board.STATE_WORDS.get(state, ""),
         # [D-D11-5: "its page marked "test one""] a design the executor marked a test, in the words it was marked with
         # (services.master_tasks) — a test marked without words (tasks 126–131) shows none
         "test_words": _test_words(task),
         "next_words": card.reason or card.next_words, "spent": float(task_cost_usd(task)),
         "cap": float(settings.MAX_COST_PER_TASK), "direction": _design_direction(task),
         # at its concept step the stage IS the choice of concept: the rail would show them twice
         "concepts": [] if task.status in ("awaiting_gate_1", "awaiting_gate1_generation_configuration")
         else _design_concepts(task)}
    from apps.pipeline.services.revision import current_revision
    return render(request, "dashboard/design.html", {
        "task": task, "d": d, "adjust": adjust, "lib": _library_offer(task, adjust), "status_words": STATUS_WORDS,
        "inspiration": _inspiration_kept(request, task, adjust),
        "page": {"task_id": task.pk, "brand_id": task.brand_id, "current_user": request.user.get_username(),
                 "build": current_revision(),
                 # why it stopped, in words, and whether it waits to be looked at again — for the step's own script
                 # (a folded test that stopped says why in words too — its raw error is the record's, never the screen's)
                 "reason": card.reason if state in (board.ATTENTION, board.TRIED_AGAIN) else "",
                 "look_again": card.status == "container_stage_visually_rejected" and state == board.WAITING,
                 # the drawing made since, shown as a picture to look at — the step's own data withholds its files
                 # (the result contract does not vouch for a design turned down), and nothing here offers it to approve
                 "look_again_picture": (board.pictures([card]).get(task.pk)
                                        if card.status == "container_stage_visually_rejected"
                                        and state == board.WAITING else None)},
    })
