"""Fresh measurements of final HAYAT files; native application census stays hash-bound.

These tests never launch Illustrator or mutate a deliverable. Known resolution,
contrast and copy-fit exceptions are checked for honest reporting, not erased.
"""
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from collections import Counter
from io import BytesIO

import fitz
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
import numpy as np
from PIL import Image
import pytest

from apps.pipeline.services import round_balm_master as master
from apps.pipeline.services import round_files_export as export
from apps.pipeline.services import stick_carton
from apps.pipeline.services import lid_master
from apps.pipeline.services import round_files_faces as faces

OUT = master.OUT
ROOTS = (OUT, OUT / "tints/fig-milk", OUT / "tints/ember")
FILES = ("body-wrap.ai", "cap-wrap.ai", "label.ai", "carton-artwork.ai", "leaflet.ai")


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def visible_draft_text(document, frame):
    """Extract only painted, printable type-layer glyphs inside this back frame.

    A document-wide live-glyph count cannot prove that the back draft is on
    a visible, printable layer inside its intended frame.
    """
    type_refs = [xref for xref, row in document.get_ocgs().items() if row["name"] == "type"]
    assert len(type_refs) == 1
    type_ref = type_refs[0]
    assert type_ref in document.get_layer().get("on", []), "type layer is hidden"
    kind, usage = document.xref_get_key(type_ref, "Usage")
    if kind == "xref":
        usage = document.xref_object(int(usage.split()[0]))
    assert "/PrintState/ON" in usage.replace(" ", ""), "type layer does not print"
    rectangle = fitz.Rect(*(value * 72 / 25.4 for value in frame["box_mm"]))
    text = []
    for span in document[0].get_texttrace():
        if span.get("layer") != "type" or span.get("opacity", 0) <= 0 or span.get("type") == 3:
            continue
        characters = []
        for codepoint, glyph, origin, bounds in span["chars"]:
            centre = fitz.Point((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
            if rectangle.contains(centre):
                characters.append(chr(codepoint))
        if characters:
            text.append("".join(characters))
    return normalized(" ".join(text))


def assert_draft_starts_visible(document, frame):
    actual = visible_draft_text(document, frame)
    words = {"en": ("HAYAT", "lip", "balm"), "es": ("Bálsamo", "labial"), "ar": ("بلسم", "شفاه")}
    assert all(word in actual or word[::-1] in actual for word in words[frame["language"]]), (
        f"{frame['language']} draft first words are not visible on the type layer: {actual!r}")


@pytest.mark.parametrize("folder", ROOTS, ids=("rosewater", "fig-milk", "ember"))
@pytest.mark.parametrize("filename", FILES)
def test_every_final_ai_has_embedded_live_fonts_five_layers_and_bound_native_census(folder, filename):
    path = folder / filename
    assert path.is_file(), path
    census = read(folder / "native-checks" / (path.stem + ".json"))
    assert census["final_sha256"] == digest(path)
    assert census["saved"] and census["final_is_native_illustrator"] and census["holds"]
    assert census["execution"]["executed"] and census["execution"]["saved"]
    reopened = census["saved_file_reopen"]
    assert reopened["reopened"] and reopened["holds"]
    assert reopened["final_sha256"] == digest(path)
    assert reopened["placed"] == 0
    if filename == "leaflet.ai":
        assert reopened["rasters"] == 0
    else:
        assert reopened["rasters"] > 0
    assert len(reopened["layers"]) == 5
    assert {row["name"] for row in reopened["layers"]} == set(master.LAYERS)
    assert all(row["locked"] and not row["printable"] for row in reopened["layers"]
               if row["name"] in ("die", "guides"))
    if filename in ("carton-artwork.ai", "leaflet.ai"):
        before = sorted(census["frames"], key=lambda row: row["text"])
        after = sorted(reopened["frames"], key=lambda row: row["text"])
        assert len(before) == len(after)
        for saved_frame, reopened_frame in zip(before, after):
            assert saved_frame["text"] == reopened_frame["text"]
            saved_characters, reopened_characters = saved_frame["characterFonts"], reopened_frame["characterFonts"]
            assert "".join(row["text"] for row in saved_characters) == saved_frame["text"]
            assert len(saved_characters) == len(reopened_characters)
            for saved_char, reopened_char in zip(saved_characters, reopened_characters):
                assert saved_char["text"] == reopened_char["text"]
                assert saved_char["font"] == reopened_char["font"]
                if saved_char["text"].isspace():
                    assert saved_char["nonprintingWhitespace"] and reopened_char["nonprintingWhitespace"]
                    assert saved_char["font"] is saved_char["size"] is reopened_char["size"] is None
                else:
                    assert saved_char["font"] in {"DMSans-Regular", "Almarai-Regular"}
                    assert saved_char["size"] == pytest.approx(reopened_char["size"], abs=.00002)
                    assert saved_char["size"] >= (6 if filename == "leaflet.ai" else 5) - .0001
    else:
        # The nine unchanged Round 1B files retain their single-font census.
        assert sorted((row["text"], row["font"]) for row in reopened["frames"]) == sorted(
            (row["text"], row["font"]) for row in census["frames"])
    assert {row["name"] for row in census["layers"]} == set(master.LAYERS)
    assert len(census["layers"]) == 5
    for row in census["layers"]:
        if row["name"] in ("die", "guides"):
            assert row["locked"] and not row["printable"]
    assert census["placed"] == 0
    if filename == "leaflet.ai":
        assert census["rasters"] == 0
    else:
        assert census["rasters"] > 0
    assert all(row["font"] in {"DMSans-Regular", "Almarai-Regular"} for row in census["frames"])
    floor = 6 if filename == "leaflet.ai" else 5
    assert all(row["size"] >= floor - .0001 for row in census["frames"])
    fresh = master.read_back_ai(path)
    assert fresh["pdf_compatible_holds"], fresh["checks"]
    assert fresh["native_illustrator_validated"]
    assert fresh["live_glyph_count"] > 0
    assert all(row["embedded_bytes"] > 0 for row in fresh["fonts"])
    assert all(any(face in row["name"].replace(" ", "") for face in ("DMSans", "Almarai"))
               for row in fresh["fonts"])
    with fitz.open(path) as document:
        assert document.page_count == census["artboards"] == 1
        # Native Illustrator private editing streams are actually in the file;
        # an .ai extension and a JSON claim alone cannot satisfy this check.
        kind, ref = document.xref_get_key(document[0].xref, "PieceInfo/Illustrator")
        assert kind == "xref"
        kind, private = document.xref_get_key(int(ref.split()[0]), "Private")
        assert kind == "xref"
        private_object = document.xref_object(int(private.split()[0]))
        streams = re.findall(r"/AIPrivateData\d+\s+(\d+) 0 R", private_object)
        assert streams and all(document.xref_is_stream(int(xref)) for xref in streams)


@pytest.mark.parametrize("folder", ROOTS, ids=("rosewater", "fig-milk", "ember"))
@pytest.mark.parametrize("filename", ("carton-artwork.ai", "leaflet.ai"))
def test_every_printed_latin_letter_uses_latin_face_and_arabic_letter_uses_arabic_face(folder, filename):
    latin_letters = arabic_letters = 0
    with fitz.open(folder / filename) as document:
        for span in document[0].get_texttrace():
            if span.get("layer") != "type" or span.get("opacity", 0) <= 0 or span.get("type") == 3:
                continue
            family = span["font"].replace(" ", "")
            for code, glyph, origin, bounds in span["chars"]:
                character = chr(code)
                if re.fullmatch(r"[A-Za-z]", character):
                    assert "DMSans" in family, (filename, character, family)
                    latin_letters += 1
                elif unicodedata.category(character).startswith("L") and "ARABIC" in unicodedata.name(character, ""):
                    assert "Almarai" in family, (filename, character, family)
                    arabic_letters += 1
        assert latin_letters > 0 and arabic_letters > 0


def test_corrupted_exported_locks_fail_fresh_readback_without_touching_original(tmp_path):
    original = OUT / "body-wrap.ai"
    original_sha = digest(original)
    changed = tmp_path / "changed.ai"
    with fitz.open(original) as document:
        document.xref_set_key(document.pdf_catalog(), "OCProperties/D/Locked", "[]")
        for xref, layer in document.get_ocgs().items():
            if layer["name"] in ("die", "guides"):
                document.xref_set_key(xref, "Usage", "<</Print<</PrintState/ON>>>>")
        document.save(changed)
    fresh = master.read_back_ai(changed)
    assert not fresh["checks"]["die_guides_locked_nonprinting"]
    assert not fresh["pdf_compatible_holds"]
    assert not fresh["native_illustrator_validated"]
    assert digest(original) == original_sha


def test_draft_moved_to_hidden_guides_fails_even_with_live_front_type(tmp_path):
    changed = tmp_path / "hidden-frame.ai"
    frame = {"language": "en", "box_mm": [15, 35, 65, 55]}
    with fitz.open() as document:
        canvas = document.new_page(width=240, height=220)
        layers = {name: document.add_ocg(name, on=name not in ("die", "guides")) for name in master.LAYERS}
        for name, xref in layers.items():
            document.xref_set_key(xref, "Usage", "<</Print<</PrintState/" +
                                  ("OFF" if name in ("die", "guides") else "ON") + ">>>>")
        canvas.insert_text((45, 50), "HAYAT front remains live", fontsize=8, oc=layers["type"])
        canvas.insert_text((45, 120), "HAYAT lip balm hidden on guides", fontsize=8, oc=layers["guides"])
        document.save(changed)
    with fitz.open(changed) as document:
        assert sum(len(span["chars"]) for span in document[0].get_texttrace()) > 0
        # The old document-wide live-glyph instrument still passes on front type.
        assert "HAYAT front remains live" in document[0].get_text("text")
        with pytest.raises(AssertionError, match="draft first words are not visible on the type layer"):
            assert_draft_starts_visible(document, frame)


def test_layer_isolation_reparses_cached_visibility_and_excludes_hidden_art(tmp_path):
    path = tmp_path / "isolated.ai"
    with fitz.open() as document:
        canvas = document.new_page(width=100, height=100)
        layers = {name: document.add_ocg(name, on=name not in ("die", "guides")) for name in master.LAYERS}
        canvas.draw_rect((10, 10, 30, 30), color=None, fill=(1, 0, 0), oc=layers["plate"])
        canvas.draw_rect((50, 50, 70, 70), color=None, fill=(0, 0, 1), oc=layers["type"])
        canvas.draw_rect((80, 10, 95, 30), color=None, fill=(0, 1, 0), oc=layers["die"])
        document.save(path)
    original_sha = digest(path)
    with fitz.open(path) as document:
        document[0].get_pixmap()  # Populate the prior viewer-state cache.
        export.set_layers(document, {"plate"})
        plate = export.raster(document, dpi=72)
        export.set_layers(document, {"type"})
        typography = export.raster(document, dpi=72)
        assert not np.array_equal(plate, typography)
        assert tuple(plate[20, 20]) == (255, 0, 0)
        assert tuple(plate[60, 60]) == (255, 255, 255)
        assert tuple(typography[20, 20]) == (255, 255, 255)
        assert tuple(typography[60, 60]) == (0, 0, 255)
        assert tuple(plate[20, 85]) == tuple(typography[20, 85]) == (255, 255, 255)
    assert digest(path) == original_sha


@pytest.mark.parametrize("folder", ROOTS, ids=("rosewater", "fig-milk", "ember"))
def test_carton_actual_die_retains_all_185_engine_segments(folder, tmp_path):
    path = folder / "carton-artwork.ai"
    coords, engine_fold = stick_carton.die(stick_carton.PRODUCTS["lip_balm"])
    origin = coords.bleed_polygon.bounds[:2]
    scratch = tmp_path / "die-visible.ai"
    with fitz.open(path) as document:
        export.set_layers(document, {"die"})
        document.save(scratch)
    actual = stick_carton.die_readback(scratch, coords, *origin)
    assert actual["segments"] == 185
    assert actual["missing_or_moved"] == 0 and actual["holds"], actual
    report = read(folder / "carton-fold-check.json")
    assert report["die_readback"]["segments"] == actual["segments"]
    assert report["die_readback"]["missing_or_moved"] == actual["missing_or_moved"]
    assert report["internal_mm"] == [20, 20, 73]
    assert engine_fold["passed"] and report["zero_crossings"]["crossings"] == 0
    # Margin overflow stays reported; it is not silently renamed a crossing.
    assert isinstance(report["zero_crossings"]["outside_the_safe_area"], list)


def source_drafts():
    previous = read(master.REPO / "docs/audit/day-12/balm/carton/carton-fit-report.json")
    result = {}
    for language in ("en", "es", "ar"):
        lines = [row for row in previous["lines"] if row["lang"] == language]
        fields = {field for row in lines for field in row["fields"]}
        assert {"description", "ingredients", "how_to_use", "warnings", "made_in", "claims"} <= fields
        text = " ".join(row["text"] for row in lines)
        result[language] = normalized(text.replace("Enchanted Rose", "HAYAT") + " (owner to confirm)")
    return result


def test_three_full_copy_fields_preserve_day12_words_with_only_recorded_replacements():
    copy = read(OUT / "leaflet-copy.json")
    assert set(copy["copy"]) == {"en", "es", "ar"}
    for language, expected in source_drafts().items():
        assert normalized(copy["copy"][language]) == expected
        assert len(copy["chunks"][language]) == 2
        assert "".join(copy["chunks"][language]) == copy["copy"][language]


@pytest.mark.parametrize("folder,tint", zip(ROOTS, ("Rosewater", "Fig Milk", "Ember")),
                         ids=("rosewater", "fig-milk", "ember"))
def test_six_native_leaflet_frames_print_every_full_draft_without_hidden_characters(folder, tint):
    fit = read(folder / "leaflet-fit-report.json")
    copy = read(folder / "leaflet-copy.json")
    census = read(folder / "native-checks/leaflet.json")
    frames = {row["name"]: row for row in census["areaFrames"]}
    specs = read(folder / "leaflet-native-frames.json")["frames"]
    expected_names = {f"leaflet {language}{part}" for language in ("en", "es", "ar") for part in (1, 2)}
    assert set(frames) == {row["name"] for row in specs} == expected_names
    assert len(census["areaFrames"]) == len(specs) == 6
    assert fit["hidden_characters"] == 0
    for language, expected in source_drafts().items():
        expected = expected.replace("Rosewater", tint)
        assert normalized(copy["copy"][language]) == expected
        assert "".join(copy["chunks"][language]) == copy["copy"][language]
        actual_copy = "".join(frames[f"leaflet {language}{part}"]["fullContents"] for part in (1, 2))
        # Layout may replace a space with a paragraph break for a mixed-script
        # suffix. Exact source drafts and exact formatted native contents are
        # checked independently; word order and punctuation stay unchanged.
        assert normalized(actual_copy) == normalized(copy["copy"][language])
    with fitz.open(folder / "leaflet.ai") as document:
        assert document.page_count == 1
        assert sum(len(row["chars"]) for row in document[0].get_texttrace()) == census["native_pdf_live_glyphs"]
        for spec in specs:
            actual = frames[spec["name"]]
            assert actual["layer"] == "type" and actual["kind"] == "TextType.AREATEXT"
            assert actual["fullContents"] == spec["copy"]
            assert actual["overflow"] is False and actual["visibleLines"]
            compact = lambda text: "".join(normalized(text).split())
            assert compact("".join(actual["visibleLines"])) == compact(actual["fullContents"])
            # Native logical order plus every printed glyph proves the full
            # text is visible, even when the PDF emits Arabic in visual order.
            assert Counter(compact(visible_draft_text(document, spec))) == Counter(compact(spec["copy"]))


@pytest.mark.parametrize("folder", ROOTS, ids=("rosewater", "fig-milk", "ember"))
def test_short_carton_copy_has_zero_hidden_characters_and_points_to_leaflet(folder):
    fit = read(folder / "carton-fit-report.json")
    census = read(folder / "native-checks/carton-artwork.json")
    frames = {row["name"].removeprefix("back regulated "): row for row in census["areaFrames"]}
    specs = read(folder / "carton-native-frames.json")["frames"]
    assert set(frames) == {"en", "es", "ar"} and len(census["areaFrames"]) == len(specs) == 3
    assert fit["hidden_characters"] == 0
    assert fit["copy_shortened"] is True
    assert fit["copy_shortening_authorization"].startswith("D-R1C-1")
    phrases = {"en": "see leaflet", "es": "ver prospecto", "ar": "انظر النشرة"}
    for language, phrase in phrases.items():
        actual = frames[language]
        assert phrase.casefold() in normalized(actual["fullContents"]).casefold()
        assert normalized(actual["fullContents"]) == normalized(fit["copy"][language])
        assert actual["layer"] == "type" and actual["kind"] == "TextType.AREATEXT"
        assert actual["overflow"] is False
        assert "".join(normalized("".join(actual["visibleLines"])).split()) == "".join(normalized(actual["fullContents"]).split())
    with fitz.open(folder / "carton-artwork.ai") as document:
        for spec in specs:
            compact = lambda text: "".join(normalized(text).split())
            assert Counter(compact(visible_draft_text(document, spec))) == Counter(compact(spec["copy"]))
    assert fit["ean"]["number"] is None
    assert fit["ean"]["drawn_ladder_mm"] == [14.45, 29.83]


@pytest.mark.parametrize("folder", ROOTS, ids=("rosewater", "fig-milk", "ember"))
def test_actual_leaflet_sheet_matches_provisional_folded_dimensions_and_bound_report(folder):
    path = folder / "leaflet.ai"
    report = read(folder / "leaflet-fold-check.json")
    with fitz.open(path) as document:
        assert [document[0].rect.width * 25.4 / 72, document[0].rect.height * 25.4 / 72] == pytest.approx([108, 71], abs=.002)
    assert report["sheet_mm"] == [108, 71] and report["folded_mm"] == [18, 71]
    assert report["inside_mm"] == [20, 20, 73]
    assert report["provisional"] is True and report["planar_fit"] is True
    assert report["crossings"] == 0 and report["holds"] is True
    assert report["native_artwork_sha256"] == digest(path)
    assert len(report["cuts"]) == 4 and len(report["folds"]) == 5


def test_known_resolution_and_fidelity_limits_are_reported_as_failures():
    record = read(OUT / "fidelity.json")
    for name, row in record["panels"].items():
        assert row["effective_ppi_at_trim"] < 300
        assert row["ppi_300_met"] is False
        assert row["holds"]["de00_mean"] == (row["de00_mean"] < row["bars"]["de00_mean_lt"])
        assert row["holds"]["de00_max"] == (row["de00_max"] < row["bars"]["de00_max_lt"])
        assert row["holds"]["ssim"] == (row["ssim"] > row["bars"]["ssim_gt"])
    assert record["all_panels_300_ppi"] is False
    assert record["all_fidelity_thresholds_pass"] is False


def outline_height_mm(path, text, point_size):
    with TTFont(path) as font:
        glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
        bounds = []
        for character in text:
            pen = BoundsPen(glyphs)
            glyphs[cmap[ord(character)]].draw(pen)
            if pen.bounds:
                bounds.append(pen.bounds)
        height = max(b[3] for b in bounds) - min(b[1] for b in bounds)
        return height / font["head"].unitsPerEm * point_size * 25.4 / 72


@pytest.mark.parametrize("folder", ROOTS, ids=("rosewater", "fig-milk", "ember"))
def test_native_body_point_sizes_match_reference_cap_metrics(folder):
    census = read(folder / "native-checks/body-wrap.json")
    report = read(folder / "wrap-type-checks.json")["body"]
    for row in report:
        matches = [frame for frame in census["frames"] if frame["text"] == row["display"]]
        assert len(matches) == 1, row["name"]
        size = matches[0]["size"]
        assert size == pytest.approx(row["size_pt"], abs=.00002)
        cap = outline_height_mm(master.REPO / row["font_path"], "ا" if row["face"] == "arabic" else "H", size)
        assert cap == pytest.approx(row["cap_height_mm"], abs=.00002)
        assert row["cap_floor_2_5mm"] == (cap >= 2.5 - .00001)
        if row["copy"] in ("HAYAT", "حياة", "LIP BALM", "بلسم شفاه"):
            assert cap >= 2.5 - .00001


@pytest.mark.parametrize("folder", ROOTS, ids=("rosewater", "fig-milk", "ember"))
@pytest.mark.parametrize("surface", ("body-wrap", "carton-artwork"))
def test_every_printed_quantity_digit_is_at_least_two_mm_and_estimated_sign_is_three_mm(folder, surface):
    census = read(folder / "native-checks" / (surface + ".json"))
    latin = export.FONT_PATHS["latin"]
    expected_copies = 1 if surface == "body-wrap" else 2
    for text in ("4.5 g", "0.15 oz"):
        actual = [frame for frame in census["frames"] if frame["text"] == text]
        assert len(actual) == expected_copies
        for frame in actual:
            heights = {digit: outline_height_mm(latin, digit, frame["size"]) for digit in set(text) if digit.isdigit()}
            assert min(heights.values()) >= 2 - .00002, heights
    with fitz.open(folder / (surface + ".ai")) as document:
        spans = {}
        for span in document[0].get_texttrace():
            if span.get("layer") == "type" and span.get("opacity", 0) > 0 and span.get("type") != 3:
                spans.setdefault("".join(chr(c[0]) for c in span["chars"]), []).append(span)
        assert len(spans["℮"]) == expected_copies
        assert len(spans["4.5 g"]) == len(spans["0.15 oz"]) == expected_copies
        minimum = min(outline_height_mm(latin, digit, span["size"])
                      for text in ("4.5 g", "0.15 oz") for span in spans[text] for digit in text if digit.isdigit())
        assert minimum >= 2, minimum
        for sign in spans["℮"]:
            assert outline_height_mm(latin, "℮", sign["size"]) == pytest.approx(3, abs=.0001)
        differences = []
        with TTFont(latin) as font:
            glyphs, cmap, units = font.getGlyphSet(), font.getBestCmap(), font["head"].unitsPerEm
            def bottom(span, character):
                pen = BoundsPen(glyphs)
                glyphs[cmap[ord(character)]].draw(pen)
                char = next(row for row in span["chars"] if chr(row[0]) == character)
                return (char[2][1] - pen.bounds[1] / units * span["size"]) * 25.4 / 72
            for grams in spans["4.5 g"]:
                gx, gy = grams["chars"][0][2]
                sign = min(spans["℮"], key=lambda row: (row["chars"][0][2][0] - gx) ** 2 + (row["chars"][0][2][1] - gy) ** 2)
                difference = abs(bottom(grams, "4") - bottom(sign, "℮"))
                assert difference < .02
                differences.append(difference)
        if surface == "body-wrap":
            measured = read(folder / "net-checks.json")["body"]
            assert measured["native_figure_min_mm"] == pytest.approx(minimum, abs=.0001)
            assert measured["native_estimated_sign_mm"] == pytest.approx(3, abs=.0001)
            assert measured["native_baseline_difference_mm"] == pytest.approx(differences[0], abs=.0001)
        else:
            fit = read(folder / "carton-fit-report.json")
            measured = fit["net_native_checks"]
            assert measured["figure_min_mm"] == pytest.approx(minimum, abs=.0001)
            assert set(fit["net_by_panel"]) == {"front", "back"}
            assert sorted(row["baseline_difference_mm"] for row in fit["net_by_panel"].values()) == pytest.approx(sorted(differences), abs=.0001)
            assert all(row["estimated_sign_height_mm"] == pytest.approx(3, abs=.0001) for row in fit["net_by_panel"].values())


@pytest.mark.parametrize("folder", ROOTS, ids=("rosewater", "fig-milk", "ember"))
@pytest.mark.parametrize("panel,height", (("body", 42), ("cap", 32)))
def test_actual_embedded_wrap_plate_has_extended_bleed_and_reported_two_mm_seam(folder, panel, height):
    from scipy.ndimage import gaussian_filter1d
    report = read(folder / "wraps.json")[panel]
    with fitz.open(folder / (panel + "-wrap.ai")) as document:
        assert [document[0].rect.width * 25.4 / 72, document[0].rect.height * 25.4 / 72] == pytest.approx([58.5, height], abs=.002)
        images = document[0].get_images(full=True)
        assert len(images) == 1
        pixels = np.asarray(Image.open(BytesIO(document.extract_image(images[0][0])["image"])).convert("RGB"))
    expected = np.asarray(Image.open(OUT / "composed-plates" / (panel + ".png")).convert("RGB"))
    assert np.array_equal(pixels, expected), "The final AI must embed the measured composed plate unchanged"
    bleed = report["bleed_rows"]
    assert report["bleed_top_bottom_mm"] == 1 and abs(bleed / pixels.shape[0] * height - 1) < .05
    assert np.all(pixels[:bleed] == pixels[bleed]) and np.all(pixels[-bleed:] == pixels[-bleed-1])
    assert report["seam"]["band_mm"] == 2
    scale = pixels.shape[1] / 58.5
    overlap = round((58.5 - np.pi * 18) * scale)
    sample = round(scale)
    left = gaussian_filter1d(pixels[:, overlap:overlap+sample].astype(float).mean(1), .5 * scale, axis=0)
    right = gaussian_filter1d(pixels[:, -sample:].astype(float).mean(1), .5 * scale, axis=0)
    delta = faces.delta_e00(faces.srgb_to_lab(left), faces.srgb_to_lab(right))
    assert float(delta.mean()) == pytest.approx(report["seam"]["after_mean"], abs=.0001)
    assert float(delta.max()) == pytest.approx(report["seam"]["after_max"], abs=.0001)
    assert report["seam"]["holds"] == (float(delta.mean()) <= 2)


@pytest.mark.parametrize("folder", ROOTS, ids=("rosewater", "fig-milk", "ember"))
def test_product_drawing_is_bound_to_current_wrap_flats(folder):
    report = read(folder / "drawing.json")
    assert report["schema"] == "product_drawing/1" and report["label"] == "drawing, not a render"
    assert [(row["band"], row["visible_mm"]) for row in report["bands"]] == [("body", 40), ("cap", 30)]
    for row in report["bands"]:
        assert digest(master.REPO / row["picture"]) == row["sha256"]
    assert digest(master.REPO / report["file"]) == report["sha256"]
    with Image.open(master.REPO / report["file"]) as drawing:
        assert drawing.format == "PNG" and min(drawing.width, drawing.height) > 100
