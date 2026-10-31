"""Day 11, D-D11-9 — the design-task pages: a finished master published as a real design task (services/master_tasks.py),
its page (/dashboard/designs/<id>/) and its status API carrying the hero, the one drawing's pages (a page per surface,
each named) and every download, the layered .ai the one Download and every other file under "Other formats" (his goal
of 2026-10-13, (5) and (6)); the task at Gate 2 and nothing approving it; a re-publish the same task; a manifest naming a
file that is not there refused before anything is written; "Test one" on the marked test's page only.

Every check runs on small files made here, never the day's records, and each has a control that must fail (a planted
fault): a touched drawing loses its page names, a changed copy fails its pin, a second key makes a second task, the
Download check refuses the extras put first, a straight create at Gate 2 notifies, a decided design is not published
over.

After the review of Day 11: the pieces carry layers as the day's .ai files do (a hidden 'foil', a shown one of the same
name on another surface), and every page of the one drawing draws pixel for pixel as its own file — the control, the
pages joined by insert_pdf alone, draws the hidden layers, and each step of carrying them taken out is refused; the
fixed files are said in the words the publication stored (the control: the carton's words come back without its
backend); every one of the owner's acts at Gate 2 refuses a re-publish alone; no ledger row appears after a publish, a
re-publish or his Approve (the control: a planted row fails the check); a slug or key with a trailing newline is
refused."""
import json
import os
import re
import shutil
import subprocess

from html import unescape

import fitz
import pytest
from PIL import Image

from apps.pipeline.services import master_tasks as mt

SLUG = "zilal-palette"
SURFACES = [("lid", "The lid"), ("inside", "Inside the lid"), ("tray", "The open tray"), ("tray-cut", "The tray's cut page"),
            ("sticker", "The back sticker"), ("box", "The box")]


@pytest.fixture(autouse=True)
def local_environment(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    # these are new test tasks, never the owner's folded task numbers
    monkeypatch.setattr("apps.dashboard.board.OWNER_FOLD", {})


def _png(path, colour):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (60, 40), colour).save(path)
    return path


def _pdf(path, *texts):
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for text in texts:
        page = doc.new_page(width=300, height=200)
        page.insert_text((30, 100), text, fontsize=18)
    doc.save(str(path))
    doc.close()
    return path


#: where a layer draws on a page: a hidden one over most of it (the masks of the day's .ai files), a shown one apart
HIDDEN_BOX, SHOWN_BOX = (0, 120, 300, 200), (200, 10, 290, 60)


def _layered(path, *pages, listed=True):
    """A PDF-compatible file with layers, as the day's .ai files are: each page its words and its layers, each layer
    ``(name, shown)`` a filled box on it — a hidden one black across the lower page, a shown one gold in a corner. A
    name named twice is ONE layer of the file (as an .ai's 'foil' is on every page it touches). ``listed=False``: the
    file keeps its layers but lists none (no /OCProperties), as the day's 1 : 1 sheets do, so it hides nothing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    made = {}
    for text, layers in pages:
        page = doc.new_page(width=300, height=200)
        page.insert_text((30, 100), text, fontsize=18)
        for name, shown in layers:
            if name not in made:
                made[name] = doc.add_ocg(name, on=shown)
            page.draw_rect(fitz.Rect(HIDDEN_BOX if not shown else SHOWN_BOX), color=None,
                           fill=(0, 0, 0) if not shown else (0.8, 0.6, 0.2), oc=made[name])
    if not listed:
        doc.xref_set_key(doc.pdf_catalog(), "OCProperties", "null")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def pieces(tmp_path):
    """A product's pieces as the day leaves them, each small: pictures, print PDFs, PDF-compatible layered .ai files,
    the 1 : 1 sheets and two records — the tray's and the inside's pictures under one name in two folders. Their
    layers are the day's own kind (Day 10's box-artwork.ai hides its 'foil', lid-master.ai its 'name', 'foil' and
    'relief'): the lid's print page shows a 'foil' while the box's and the sticker's .ai hide theirs under the same name,
    the tray's two-page PDF — one file named for two surfaces — hides a 'varnish' on both pages, and the inside's PDF
    keeps an 'artwork' layer it lists nowhere (no /OCProperties, as the day's 1 : 1 sheets), so it hides nothing."""
    src = tmp_path / "day"
    return {
        "hero": _png(src / "lid" / "lid-master-flat.png", (40, 30, 90)),
        "concept": _png(src / "sketch" / "lid.png", (60, 40, 110)),
        "lid_pdf": _layered(src / "lid" / "lid-master.pdf", ("LID FACE", [("foil", True)]), ("LID FOIL PLATE", [])),
        "lid_ai": _layered(src / "lid" / "lid-master.ai", ("LID LAYERED", [("name", False), ("logo", True)])),
        "lid_a4": _pdf(src / "lid" / "lid-1to1-A4.pdf", "LID AT 1:1"),
        "inside_pdf": _layered(src / "inside-lid" / "inside-lid.pdf", ("INSIDE", [("artwork", True)]), listed=False),
        "inside_png": _png(src / "inside-lid" / "picture.png", (200, 190, 230)),
        "tray_pdf": _layered(src / "tray" / "tray-artwork.pdf", ("TRAY", [("varnish", False)]),
                             ("TRAY CUT", [("varnish", False), ("cut", True)])),
        "tray_png": _png(src / "tray" / "picture.png", (90, 140, 150)),
        "sticker_ai": _layered(src / "sticker" / "sticker.ai", ("STICKER", [("artwork", True), ("foil", False)])),
        "sticker_pdf": _pdf(src / "sticker" / "sticker.pdf", "STICKER PDF"),
        "box_ai": _layered(src / "box" / "box-artwork.ai", ("BOX", [("artwork", True), ("foil", False)])),
        "box_pdf": _pdf(src / "box" / "box-artwork.pdf", "BOX", "BOX INSIDE", "BOX CUT"),
        "box_a3": _pdf(src / "box" / "box-1to1-A3.pdf", "BOX AT 1:1"),
        "fidelity": _record(src / "lid" / "fidelity.json", {"verdict": {"holds": True}}),
        "verdict": _record(src / "lid" / "jury" / "verdict.json", {"for_the_record": True}),
    }


def _record(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def manifest(p, slug=SLUG, target="palette", test_words=None, product_id="TEST-D11-ZILAL",
             name="Zilal Eyeshadow Palette"):
    s = {k: str(v) for k, v in p.items()}
    surface = {"lid": (s["lid_pdf"], 1, s["lid_ai"], s["hero"], [s["lid_a4"]]),
               "inside": (s["inside_pdf"], 1, None, s["inside_png"], []),
               "tray": (s["tray_pdf"], 1, None, s["tray_png"], []),
               "tray-cut": (s["tray_pdf"], 2, None, None, []),
               "sticker": (s["sticker_ai"], 1, s["sticker_ai"], None, [s["sticker_pdf"]]),
               "box": (s["box_ai"], 1, s["box_ai"], None, [s["box_pdf"], s["box_a3"]])}
    return {"schema": mt.MANIFEST_SCHEMA, "slug": slug, "target": target,
            "task_text": "BBROSE eyeshadow palette, 18 shades, 190 x 120 x 12 mm closed (the Day 11 master)",
            "product": {"product_id": product_id, "name": name, "name_ar": "ظلال", "year": 2026},
            "concept": {"picture": s["concept"], "direction": "B-1.3, the floated stones", "owner_picked": True},
            "hero": s["hero"], "primary": "lid",
            "surfaces": [{"key": key, "title": title, "page": {"file": surface[key][0], "number": surface[key][1]},
                          "layered": surface[key][2], "picture": surface[key][3], "others": surface[key][4]}
                         for key, title in SURFACES],
            "evidence": [{"file": s["fidelity"], "words": "The lid's fidelity record"},
                         {"file": s["verdict"], "words": "The jury's verdict, for the record"}],
            "test_words": test_words}


@pytest.fixture
def owner(db, client):
    from django.contrib.auth.models import Group, User

    from apps.core.models import Brand
    user = User.objects.create_superuser("day11-owner", password="test-only")
    Brand.objects.create(name="BBROSE", master_brief="the house brief")
    reviewer = User.objects.create_user("day11-reviewer", email="reviewer@example.invalid")
    reviewer.groups.add(Group.objects.get_or_create(name="Reviewer")[0])
    client.force_login(user)
    return user


def _files_url(rel):
    return "/files/" + rel


def _no_paid_call():
    """Not one row in the cost ledger, whichever task it would name: no image, model or search call was made
    (``test_the_no_paid_call_check_sees_a_planted_ledger_row`` is its control)."""
    from apps.pipeline.models import ApiCallRecord
    assert not ApiCallRecord.objects.exists(), list(ApiCallRecord.objects.values_list("provider", "operation"))


def _expected_other_files():
    """Every file but the layered lid (the one Download) and the hero (the page's picture — the lid's own picture,
    named twice, copied and shown once), each once: the sticker's and the box's .ai named as page and layered file
    once, the tray's PDF for its artwork and its cut page once."""
    folder = "dielines/day11/%s/" % SLUG
    return [folder + rel for rel in (
        "lid/lid-master.pdf", "lid/lid-1to1-A4.pdf",
        "inside/inside-lid.pdf", "inside/picture.png",
        "tray/tray-artwork.pdf", "tray/picture.png",
        "sticker/sticker.ai", "sticker/sticker.pdf",
        "box/box-artwork.ai", "box/box-artwork.pdf", "box/box-1to1-A3.pdf",
        "evidence/lid-fidelity.json", "evidence/jury-verdict.json")]


# --- the page and its status ------------------------------------------------------------------------------------------

def test_the_published_master_is_a_task_at_gate_2_whose_page_and_status_carry_every_surface_and_download(
        owner, client, pieces, settings):
    from apps.pipeline.models import ApiCallRecord, DesignTask, GateDecision, Notification

    made = mt.publish(manifest(pieces))
    task = DesignTask.objects.get(pk=made["task_id"])
    assert made["created"] and made["url"] == "/dashboard/designs/%d/" % task.pk
    assert (task.status, task.design_target, task.created_by) == ("awaiting_gate_2", "palette", None)
    assert task.options["spend_held"] is True and "test_run" not in task.options
    assert task.product.name == "Zilal Eyeshadow Palette" and task.product.name_ar == "ظلال"
    # nothing approves it: no gate decision, no acceptance, no final output, no paid call, no notification fan-out
    output = task.current_output()
    assert not output.is_final_approved and not GateDecision.objects.filter(task=task).exists()
    assert not task.design_acceptances.exists() and not ApiCallRecord.objects.filter(task=task).exists()
    assert not Notification.objects.filter(task=task).exists()

    status = client.get("/api/tasks/%d/status/" % task.pk)
    assert status.status_code == 200
    data = status.json()
    po = data["packaging_output"]
    folder = "/files/dielines/day11/%s/" % SLUG
    assert data["status"] == "awaiting_gate_2" and data["sku"] == "TEST-D11-ZILAL" and data["sku_from_product"]
    assert po["design_preview_url"] == folder + "hero/lid-master-flat.png"
    assert po["native_ai_url"] == folder + "lid/lid-master.ai"
    assert po["design_preview_ai_url"] == folder + "zilal-palette-every-surface.ai"
    assert [f["url"] for f in po["other_files"]] == [_files_url(rel) for rel in _expected_other_files()]
    assert all(f["words"] for f in po["other_files"])
    assert len(data["images"]) == 1 and data["images"][0]["is_approved"]

    # the one drawing: a page per surface, each named, each picture served
    views = client.get("/api/tasks/%d/drawing/" % task.pk).json()["views"]
    assert [v["words"] for v in views] == [title for _key, title in SURFACES]
    with fitz.open(os.path.join(settings.MEDIA_ROOT, po["design_preview_ai_url"][len("/files/"):])) as drawing:
        assert [drawing[n].get_text().strip() for n in range(len(drawing))] == [
            "LID FACE", "INSIDE", "TRAY", "TRAY CUT", "STICKER", "BOX"]
    for view in views:
        picture = client.get(view["thumb"])
        assert picture.status_code == 200 and picture["Content-Type"] == "image/png"

    # every address the page offers is served by the files door
    for url in [po["design_preview_url"], po["native_ai_url"], po["design_preview_ai_url"]] + [
            f["url"] for f in po["other_files"]] + [data["images"][0]["image_url_display"]]:
        assert client.get(url).status_code == 200, url

    page = client.get("/dashboard/designs/%d/" % task.pk)
    assert page.status_code == 200
    assert "Zilal Eyeshadow Palette" in page.content.decode() and "Test one" not in page.content.decode()
    assert client.get("/dashboard/designs/%d/adjust/" % task.pk).status_code == 200
    assert mt.checked(SLUG)["task_id"] == task.pk
    _no_paid_call()


def test_the_no_paid_call_check_sees_a_planted_ledger_row(owner):
    """The control for every ``_no_paid_call``: one ledger row, of no task, planted — and the check fails."""
    from apps.pipeline.models import ApiCallRecord
    _no_paid_call()
    ApiCallRecord.objects.create(provider="openai", model="planted-control", operation="control")
    with pytest.raises(AssertionError):
        _no_paid_call()


def test_the_lipstick_published_as_packaging_has_its_page_and_status(owner, client, pieces, tmp_path, settings):
    made = mt.publish(manifest(pieces, slug="wild-rose-lipstick", target="packaging", product_id="TEST-D11-LIP",
                               name="Wild Rose Lipstick"))
    status = client.get("/api/tasks/%d/status/" % made["task_id"])
    assert status.status_code == 200
    assert status.json()["design_target"] == "packaging"
    assert status.json()["packaging_output"]["native_ai_url"].endswith("/wild-rose-lipstick/lid/lid-master.ai")
    page = client.get(made["url"])
    assert page.status_code == 200 and "Wild Rose Lipstick" in page.content.decode()
    _no_paid_call()

    # a wrap has no dieline: its hero is headed neutrally on both screens though its target is 'packaging'
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the page's script is not run here")
    data = status.json()
    drawn = _screens(node, data, "Packaging", tmp_path, settings)
    assert _hero_heading(drawn["gate2"]) == "The design" and _hero_alt(drawn["completed"]) == "The design"
    # the control: the same payload as any other packaging design's — the dieline heading comes back
    data["packaging_output"]["spec_sheet"].pop("backend")
    other = _screens(node, data, "Packaging", tmp_path, settings)
    assert _hero_heading(other["gate2"]) == "The outside, on its dieline"
    assert _hero_alt(other["completed"]) == "Design on dieline"


def test_the_page_names_hold_while_the_drawing_is_the_one_written_and_fall_back_when_it_is_touched(
        owner, client, pieces):
    """The control: the names are kept with the drawing's fingerprint (path, size, time) — touched, the page reads the
    drawing's generic page names, so the names seen above are the ones this publication wrote."""
    made = mt.publish(manifest(pieces))
    output = mt_output(made)
    path = output.design_preview_ai.path
    stat = os.stat(path)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10 ** 9))
    words = [v["words"] for v in client.get("/api/tasks/%d/drawing/" % made["task_id"]).json()["views"]]
    assert words[0] == "The outside" and words[1] == "Page 2" and "The lid" not in words


def mt_output(made):
    from apps.pipeline.models import PackagingOutput
    return PackagingOutput.objects.get(pk=made["output_id"])


# --- the one drawing's pages and their layers -------------------------------------------------------------------------

def _drawn(page, zoom):
    return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)


def _sources(m):
    """(file, page number, title) of each surface's page, in the drawing's order."""
    return [(s["page"]["file"], s["page"]["number"], s["title"]) for s in m["surfaces"]]


def test_each_page_of_the_one_drawing_draws_as_its_own_file_with_its_hidden_layers_hidden(owner, pieces, settings):
    """The drawing's every page, drawn at two scales, is pixel for pixel its own file's page drawn alone — the hidden
    layers hidden, a layer of one name shown on one surface and hidden on another each in its own state, the tray's
    one file named for two surfaces both times; the thumbnail the page shows of the box is the box's own. The control:
    the same pages joined as before (insert_pdf alone) draw the hidden layers on the four surfaces that have them."""
    from apps.pipeline import drawing_views

    m = manifest(pieces)
    made = mt.publish(m)
    output = mt_output(made)
    sources = _sources(m)
    with fitz.open(output.design_preview_ai.path) as drawing:
        assert len(drawing) == len(sources)
        for n, (file, number, title) in enumerate(sources):
            with fitz.open(file) as own:
                for zoom in (mt.PROOF_SCALE, 3.0):
                    assert _drawn(drawing[n], zoom).samples == _drawn(own[number - 1], zoom).samples, (title, zoom)
        # every layer its page's own, in its own file's state, listed in the drawing's layers
        layers = {(int(drawing.xref_get_key(xref, mt.LAYER_PAGE_KEY)[1]), info["name"]): info["on"]
                  for xref, info in drawing.get_ocgs().items()}
        panel = [c["text"] for c in drawing.layer_ui_configs() if c["depth"] == 0]
    assert layers == {(1, "foil"): True, (2, "artwork"): True, (3, "varnish"): False, (4, "varnish"): False,
                      (4, "cut"): True, (5, "artwork"): True, (5, "foil"): False, (6, "artwork"): True,
                      (6, "foil"): False}
    assert panel == ["The lid", "Inside the lid", "The open tray", "The tray's cut page", "The back sticker", "The box"]
    with fitz.open(sources[1][0]) as inside:                    # the inside's file lists no layer, and draws its own
        assert not inside.get_ocgs() and inside.xref_get_key(inside.pdf_catalog(), "OCProperties")[0] == "null"

    task = output.task
    box = drawing_views.picture(task, 6, drawing_views.THUMB_PX, None, output=output)
    with fitz.open(sources[5][0]) as own:
        page = own[sources[5][1] - 1]
        assert fitz.Pixmap(box).samples == _drawn(page, drawing_views.THUMB_PX / page.rect.width).samples

    # the control: the pages joined by insert_pdf alone, as the drawing was built before
    plain = fitz.open()
    for file, number, _title in sources:
        with fitz.open(file) as own:
            plain.insert_pdf(own, from_page=number - 1, to_page=number - 1)
    joined = fitz.open(stream=plain.tobytes(garbage=3, deflate=True, no_new_id=True), filetype="pdf")
    differ = []
    for n, (file, number, title) in enumerate(sources):
        with fitz.open(file) as own:
            if _drawn(joined[n], mt.PROOF_SCALE).samples != _drawn(own[number - 1], mt.PROOF_SCALE).samples:
                differ.append(title)
    joined.close()
    plain.close()
    assert differ == ["The open tray", "The tray's cut page", "The back sticker", "The box"]


@pytest.mark.parametrize("fault, refused", [
    # no layer states written: every hidden layer draws, as insert_pdf alone left them
    ("_ocproperties", ["The open tray", "The tray's cut page", "The back sticker", "The box"]),
    # the layers not kept each its page's own: the lid's shown 'foil' and the sticker's and box's hidden ones are
    # merged (garbage=3) into one layer, hidden — so the lid draws without its foil (4,500 of 60,000 px, measured)
    ("_tag", ["The lid"]),
])
def test_a_drawing_whose_page_does_not_draw_as_its_own_file_is_refused_before_anything_is_written(
        owner, pieces, settings, monkeypatch, fault, refused):
    """The check's planted faults: each step of carrying the layers taken out in turn, and the manifest is refused —
    every page that draws otherwise named, its print PDF named as the page to give — with nothing written."""
    from apps.pipeline.models import DesignTask
    monkeypatch.setattr(mt, fault, lambda *args: None)
    with pytest.raises(mt.Refused) as said:
        mt.publish(manifest(pieces))
    problems = said.value.problems
    assert problems and all("does not draw in the one drawing as it draws in its own file" in p
                            and "give its print PDF's page instead" in p for p in problems), problems
    named = [title for _file, _number, title in _sources(manifest(pieces)) if any(
        p.startswith("the page of %s (" % title) for p in problems)]
    assert named == refused and len(problems) == len(refused), problems
    assert not DesignTask.objects.exists()
    assert not os.path.exists(os.path.join(settings.MEDIA_ROOT, "dielines"))


def test_a_page_whose_file_holds_one_layer_name_shown_and_hidden_is_refused_by_name(owner, pieces, tmp_path):
    """Two layers of one name, one shown and one hidden, cannot be told apart once copied: the page is refused, its
    print PDF named. The control: the same file with both layers shown is read."""
    def clash(path, second_shown):
        doc = fitz.open()
        page = doc.new_page(width=300, height=200)
        page.insert_text((30, 100), "BOX", fontsize=18)
        for shown, box in ((True, SHOWN_BOX), (second_shown, HIDDEN_BOX)):
            page.draw_rect(fitz.Rect(box), color=None, fill=(0, 0, 0), oc=doc.add_ocg("foil", on=shown))
        doc.save(str(path))
        doc.close()
        return str(path)

    bad = manifest(pieces)
    bad["surfaces"][5]["page"]["file"] = clash(tmp_path / "day" / "box" / "box-clash.ai", False)
    with pytest.raises(mt.Refused, match=r"The box \(box-clash\.ai, page 1\) carries two layers named 'foil', one "
                                         r"shown and one hidden.*give its print PDF's page instead"):
        mt.read(bad)
    good = manifest(pieces)
    good["surfaces"][5]["page"]["file"] = clash(tmp_path / "day" / "box" / "box-shown.ai", True)
    assert mt.read(good)["drawing_bytes"]


# --- a re-publish -----------------------------------------------------------------------------------------------------

def test_publishing_twice_updates_the_same_task_and_a_new_key_makes_a_new_one(owner, client, pieces):
    from apps.core.models import Product
    from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput

    first = mt.publish(manifest(pieces))
    drawing = mt_output(first).design_preview_ai.path
    before = os.stat(drawing).st_mtime_ns
    again = mt.publish(manifest(pieces))
    assert (again["task_id"], again["output_id"], again["created"]) == (first["task_id"], first["output_id"], False)
    assert again["written"] == [] and os.stat(drawing).st_mtime_ns == before      # the same bytes are left alone
    assert DesignTask.objects.count() == 1 and PackagingOutput.objects.count() == 1
    assert GeneratedImage.objects.count() == 1 and Product.objects.count() == 1

    # a piece changed: the copy and its pin follow, on the same task
    _png(pieces["tray_png"], (10, 200, 200))
    third = mt.publish(manifest(pieces))
    assert third["task_id"] == first["task_id"] and third["written"] == ["dielines/day11/%s/tray/picture.png" % SLUG]
    assert mt.checked(SLUG)["files"]["dielines/day11/%s/tray/picture.png" % SLUG]["sha256"] == mt._sha(
        pieces["tray_png"])

    # the control: another key is another task
    other = mt.publish(manifest(pieces, slug="golden-hour-palette", product_id="TEST-D11-GOLDEN",
                                name="Golden Hour Eyeshadow Palette"))
    assert other["task_id"] != first["task_id"] and DesignTask.objects.count() == 2
    _no_paid_call()


def test_a_design_the_owner_decided_on_is_never_published_over(owner, pieces):
    from apps.pipeline.models import DesignTask

    made = mt.publish(manifest(pieces))
    assert mt.publish(manifest(pieces))["task_id"] == made["task_id"]          # the control: at Gate 2 it updates
    DesignTask.objects.filter(pk=made["task_id"]).update(status="completed")
    with pytest.raises(mt.Refused, match="not at Gate 2"):
        mt.publish(manifest(pieces))


@pytest.mark.parametrize("act, said", [
    ("acceptance", "carries the owner's own act on its design"),
    ("gate_2_decision", "has a Gate 2 decision on record"),
    ("final_output", "has an approved output"),
])
def test_each_act_of_the_owner_keeps_a_design_still_at_gate_2_from_being_published_over(owner, pieces, act, said):
    """Each of the owner's acts alone, the design still at Gate 2 (so the status's own refusal does not fire): his
    acceptance of its drawing, a Gate 2 decision on record, an approved output — each refuses the re-publish in its
    own words, the only problem named, and no copy is written over (a changed piece stays unpublished)."""
    from django.utils import timezone

    from apps.dashboard.models import DesignAcceptance
    from apps.pipeline.models import DesignTask, GateDecision, PackagingOutput

    made = mt.publish(manifest(pieces))
    task = DesignTask.objects.get(pk=made["task_id"])
    if act == "acceptance":
        DesignAcceptance.objects.create(task=task, output=mt_output(made), decision=DesignAcceptance.ACCEPTED,
                                        decided_by=owner, decided_at=timezone.now(), preview_sha256="a" * 64,
                                        preview_name="hero/lid-master-flat.png")
    elif act == "gate_2_decision":
        GateDecision.objects.create(task=task, gate="gate_2", decision="approve", decided_by=owner)
    else:
        PackagingOutput.objects.filter(pk=made["output_id"]).update(is_final_approved=True)
    assert DesignTask.objects.get(pk=task.pk).status == "awaiting_gate_2"
    _png(pieces["tray_png"], (1, 2, 3))
    with pytest.raises(mt.Refused) as refused:
        mt.publish(manifest(pieces))
    assert refused.value.problems == ["design %d %s" % (task.pk, said)]
    assert mt.checked(SLUG)["task_id"] == task.pk                               # every copy still the one published
    _no_paid_call()


def test_a_changed_copy_fails_its_pin(owner, pieces, settings):
    mt.publish(manifest(pieces))
    assert mt.checked(SLUG)
    copy = os.path.join(settings.MEDIA_ROOT, "dielines/day11/%s/box/box-1to1-A3.pdf" % SLUG)
    with open(copy, "ab") as f:
        f.write(b"\n% changed")
    with pytest.raises(mt.Changed, match="box-1to1-A3.pdf changed"):
        mt.checked(SLUG)


# --- refusals ---------------------------------------------------------------------------------------------------------

def test_a_manifest_naming_a_file_that_is_not_there_is_refused_before_anything_is_written(owner, pieces, settings):
    from apps.core.models import Product
    from apps.pipeline.models import DesignTask

    bad = manifest(pieces)
    bad["surfaces"][4]["others"].append(str(pieces["sticker_pdf"].with_name("sticker-missing.pdf")))
    with pytest.raises(mt.Refused, match="sticker-missing.pdf is not there"):
        mt.publish(bad)
    assert not os.path.exists(os.path.join(settings.MEDIA_ROOT, "dielines"))
    assert not DesignTask.objects.exists() and not Product.objects.exists()


@pytest.mark.parametrize("fault, said", [
    (lambda m: m["surfaces"][3]["page"].update(number=3), "past the 2 page"),
    (lambda m: m.update(hero=m["surfaces"][0]["page"]["file"]), "is not a .png"),
    (lambda m: m.update(primary="inside"), "has no layered .ai"),
    (lambda m: m["surfaces"].append(dict(m["surfaces"][0])), "is not a fresh lower-case word"),
    (lambda m: m.update(target="product_container"), "is not one of palette, packaging"),
    (lambda m: m.pop("evidence"), "lacks evidence"),
    (lambda m: m.update(colour="indigo"), "carries colour"),
    # a trailing newline past the pattern's ``$`` (SLUG.match let it into a folder name and a task key)
    (lambda m: m.update(slug=SLUG + "\n"), "is not lower-case words joined by hyphens"),
    (lambda m: m["surfaces"][1].update(key="inside\n"), "is not a fresh lower-case word"),
])
def test_each_fault_in_a_manifest_is_refused_by_name_and_nothing_is_written(owner, pieces, settings, fault, said):
    from apps.pipeline.models import DesignTask
    bad = manifest(pieces)
    fault(bad)
    with pytest.raises(mt.Refused, match=said):
        mt.publish(bad)
    assert not DesignTask.objects.exists()
    assert not os.path.exists(os.path.join(settings.MEDIA_ROOT, "dielines"))


def test_a_slug_is_matched_whole():
    """The control for the two trailing-newline faults above: the pattern's ``match`` lets the newline through (as
    read() did), so the refusals are the whole match's."""
    assert mt.SLUG.match(SLUG + "\n") and mt.SLUG.match("inside\n")
    assert not mt.SLUG.fullmatch(SLUG + "\n") and not mt.SLUG.fullmatch("inside\n") and mt.SLUG.fullmatch(SLUG)


def test_a_picture_that_is_not_a_png_is_refused(owner, pieces):
    fake = pieces["hero"].with_name("fake.png")
    fake.write_bytes(b"%PDF-1.7 not a picture")
    bad = manifest(pieces)
    bad["hero"] = str(fake)
    with pytest.raises(mt.Refused, match="is not a PNG picture"):
        mt.publish(bad)


def test_a_straight_create_at_gate_2_would_notify_every_reviewer(owner):
    """The control for the publication's silence: the same task made straight at Gate 2 fans out to the reviewer."""
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, Notification
    task = DesignTask.objects.create(brand=Brand.objects.get(name="BBROSE"), task_text="x", status="awaiting_gate_2")
    assert Notification.objects.filter(task=task).exists()


# --- "Test one" -------------------------------------------------------------------------------------------------------

def test_test_one_is_on_the_marked_tests_page_only(owner, client, pieces):
    from apps.dashboard import board
    from apps.pipeline.models import DesignTask

    golden = mt.publish(manifest(pieces, slug="golden-hour-palette", test_words="Test one",
                                 product_id="TEST-D11-GOLDEN", name="Golden Hour Eyeshadow Palette"))
    zilal = mt.publish(manifest(pieces))
    page = client.get(golden["url"]).content.decode()
    assert '<span class="tag line test-mark">Test one</span>' in page
    assert "Test one" not in client.get(zilal["url"]).content.decode()           # the control
    golden_task = DesignTask.objects.get(pk=golden["task_id"])
    assert golden_task.options["test_run"] is True
    assert board.classify([golden_task], fold_old=False)[0].fold == "test"       # folded under the owner's tests
    assert board.classify([DesignTask.objects.get(pk=zilal["task_id"])], fold_old=False)[0].fold == ""
    # a test marked without words (the executor's tests 126–131) carries none
    DesignTask.objects.filter(pk=golden["task_id"]).update(options={"test_run": True, "spend_held": True})
    assert "Test one" not in client.get(golden["url"]).content.decode()


# --- the one Download and Other formats, drawn by the page's own script -----------------------------------------------

def _download_split(html):
    """(the Download's address, the addresses under Other formats) of the first download block in ``html``."""
    block = html[html.index('<div class="download-one">'):]
    main = re.search(r'<a href="([^"]+)"[^>]*class="btn [a-z]+ download-main">Download</a>', block).group(1)
    more = block[block.index('<details class="download-more">'):block.index("</details>")]
    return main, re.findall(r'<a href="([^"]+)"', more)


def _download_words(html):
    """(the words beside the Download, the words of each file under Other formats) of the first download block."""
    block = html[html.index('<div class="download-one">'):]
    main = unescape(re.search(r'<span class="download-what">([^<]*)</span>', block).group(1))
    more = block[block.index('<details class="download-more">'):block.index("</details>")]
    return main, [unescape(words) for words in re.findall(r'<a href="[^"]+"[^>]*>([^<]*)</a>', more)]


def _hero_heading(html):
    return unescape(re.search(r'<div class="drawing-hero"><h3>([^<]*)</h3>', html).group(1))


def _hero_alt(html):
    return unescape(re.search(r'<div class="drawing-hero"><img src="[^"]*" alt="([^"]*)"', html).group(1))


def _screens(node, data, label, tmp_path, settings):
    """The Gate-2 and the finished screens (and the extras-first control) drawn by the page's own script from the
    status payload ``data``, its target said as ``label`` (as the page passes it)."""
    payload = tmp_path / "status.json"
    payload.write_text(json.dumps(data), encoding="utf-8")
    js = os.path.join(settings.BASE_DIR, "static", "js")
    run = subprocess.run([node, "-e", _HARNESS, os.path.join(js, "api.js"), os.path.join(js, "gates.js"), str(payload),
                          label], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


_HARNESS = r"""
const vm = require('vm'), fs = require('fs');
const [api, gates, payload, label] = process.argv.slice(1);
const els = {};
const el = id => els[id] || (els[id] = {id, style: {}, innerHTML: '', textContent: '', value: '',
  classList: {add() {}, remove() {}, toggle() {}}, appendChild() {}, querySelectorAll: () => [], querySelector: () => null,
  setAttribute() {}, addEventListener() {}});
const ctx = {console, setTimeout, clearTimeout, setInterval, clearInterval, JSON, Math,
  document: {getElementById: el, addEventListener() {}, querySelectorAll: () => [], querySelector: () => null,
             createElement: () => el('made'), cookie: ''},
  location: {pathname: '/'}, history: {pushState() {}}, fetch: async () => ({ok: false, json: async () => ({})})};
ctx.window = ctx;
vm.createContext(ctx);
// the page's other scripts' helpers these screens call (viewer.js, poll.js, render.js's concept history, the time of
// his acts in words): none of them draws a download, each is drawn by its own tests
for (const name of ['showDrawings', 'startPolling', 'designHistoryHtml', 'whenWords']) ctx[name] = () => '';
vm.runInContext(fs.readFileSync(api, 'utf8'), ctx);
vm.runInContext(fs.readFileSync(gates, 'utf8'), ctx);
ctx.DATA = JSON.parse(fs.readFileSync(payload, 'utf8'));
ctx.LABEL = label;
vm.runInContext("showGate2(DATA.packaging_output, DATA.id, DATA.gate_decisions, DATA.images, LABEL, DATA);" +
                "showCompleted(DATA);" +
                "var CONTROL = downloadHtml([...otherFiles(DATA.packaging_output)," +
                " {url: DATA.packaging_output.native_ai_url, words: 'the layered .ai'}], '', true);", ctx);
console.log(JSON.stringify({gate2: el('mockup-view').innerHTML, completed: el('complete-state').innerHTML,
                            control: ctx.CONTROL}));
"""


def test_the_layered_file_is_the_one_download_and_every_other_file_is_under_other_formats(
        owner, client, pieces, tmp_path, settings):
    """The status API's own payload drawn by the page's own script (static/js/gates.js, in node): at Gate 2 and once
    finished, the Download is the layered .ai and every other file sits under Other formats, after the fixed ones."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the page's script is not run here (the serializer is tested above)")
    made = mt.publish(manifest(pieces))
    data = client.get("/api/tasks/%d/status/" % made["task_id"]).json()
    po = data["packaging_output"]
    drawn = _screens(node, data, "Palette", tmp_path, settings)
    extras = [f["url"] for f in po["other_files"]]
    for screen in ("gate2", "completed"):
        main, more = _download_split(drawn[screen])
        assert main == po["native_ai_url"], screen
        assert more[0] == po["design_preview_ai_url"] and more[-len(extras):] == extras, screen
    assert '<summary>Other formats</summary>' in drawn["completed"]
    # the control: the same files with the extras first — the check finds the Download is not the layered .ai
    main, more = _download_split(drawn["control"])
    assert main != po["native_ai_url"] and po["native_ai_url"] in more

    # each fixed file in the words its publication stored: the Download the lid's own layered .ai, the drawing every
    # surface — never a carton's "every piece its own" or "one layer"; the hero headed without a dieline
    words = po["spec_sheet"][mt.SLOT_WORDS_KEY]
    assert words == {"native_ai": "The lid — lid-master.ai, layered file (.ai)",
                     "design_preview_ai": "Every surface, a page each — zilal-palette-every-surface.ai"}
    for screen in ("gate2", "completed"):
        said, more_words = _download_words(drawn[screen])
        assert said == words["native_ai"] and more_words[0] == words["design_preview_ai"], screen
        assert "every piece its own" not in drawn[screen] and "one layer" not in drawn[screen], screen
        assert more_words[-len(extras):] == [f["words"] for f in po["other_files"]], screen
    assert _hero_heading(drawn["gate2"]) == "The design" and _hero_alt(drawn["completed"]) == "The design"
    # a master published before its words were stored is said neutrally, never in the carton's words
    stored = data["packaging_output"]["spec_sheet"].pop(mt.SLOT_WORDS_KEY)
    unsaid = _screens(node, data, "Palette", tmp_path, settings)
    for screen in ("gate2", "completed"):
        said, more_words = _download_words(unsaid[screen])
        assert (said, more_words[0]) == ("The layered .ai", "Every surface, a page each"), screen
    data["packaging_output"]["spec_sheet"][mt.SLOT_WORDS_KEY] = stored
    # the control: the same payload but for its backend — the carton's fixed words come back on both screens
    data["packaging_output"]["spec_sheet"].pop("backend")
    other = _screens(node, data, "Palette", tmp_path, settings)
    for screen in ("gate2", "completed"):
        said, more_words = _download_words(other[screen])
        assert said == "The .ai — Illustrator, layered, every piece its own", screen
        assert more_words[0] == "The design .ai, one layer", screen


# --- the owner's Approve click, on a test task in the test database ---------------------------------------------------

def test_the_owners_approve_click_finishes_the_published_design_with_its_names_and_downloads(
        owner, client, pieces, tmp_path, settings):
    """What his click does on the page (gates.js ``approveGate2``): his acceptance of exactly this drawing first, then
    Gate 2 — and the design is finished: its output final, its drawing's pages still named, the finished screen's one
    Download the layered .ai with every other file under Other formats, its specification, its record and the Library
    open. Nothing here is his database: the task is this test's own. The control: before the click, nothing is final."""
    from apps.pipeline.models import DesignTask, GateDecision

    settings.OWNER_ACCOUNT = "day11-owner"
    made = mt.publish(manifest(pieces))
    task_id = made["task_id"]
    data = client.get("/api/tasks/%d/status/" % task_id).json()
    da = data["design_acceptance"]
    assert not mt_output(made).is_final_approved and da["viewer_is_owner"] and da["at_its_gate"]   # the control
    accepted = client.post(da["url"], {"output_id": da["output_id"], "preview_sha256": da["preview_sha256"],
                                       "decision": "ACCEPTED", "note": ""})
    assert accepted.status_code == 200, accepted.content
    approved = client.post("/api/tasks/%d/gate2_approve/" % task_id, {"packaging_output_id": made["output_id"]})
    assert approved.status_code == 200, approved.content
    _no_paid_call()                                                             # his click pays nothing

    task = DesignTask.objects.get(pk=task_id)
    assert task.status == "completed" and mt_output(made).is_final_approved
    assert GateDecision.objects.filter(task=task, gate="gate_2", decision="approve").exists()
    assert [v["words"] for v in client.get("/api/tasks/%d/drawing/" % task_id).json()["views"]] == [
        title for _key, title in SURFACES]
    for url in ("/api/tasks/%d/download_spec/" % task_id, "/dashboard/history/tasks/%d/" % task_id,
                "/dashboard/library/finished/", "/dashboard/library/finished/%d/" % made["output_id"], made["url"]):
        assert client.get(url).status_code == 200, url
    with pytest.raises(mt.Refused, match="not at Gate 2"):                       # a finished design is never published over
        mt.publish(manifest(pieces))
    _no_paid_call()

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the finished screen is not drawn here")
    done = client.get("/api/tasks/%d/status/" % task_id).json()
    completed = _screens(node, done, "Palette", tmp_path, settings)["completed"]
    main, more = _download_split(completed)
    po = done["packaging_output"]
    assert main == po["native_ai_url"] and more[-len(po["other_files"]):] == [f["url"] for f in po["other_files"]]
    assert "/api/tasks/%d/download_spec/" % task_id in more
    said, more_words = _download_words(completed)
    assert said == po["spec_sheet"][mt.SLOT_WORDS_KEY]["native_ai"]
    assert more_words[0] == po["spec_sheet"][mt.SLOT_WORDS_KEY]["design_preview_ai"]
