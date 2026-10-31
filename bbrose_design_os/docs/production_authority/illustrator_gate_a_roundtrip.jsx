/*
 * illustrator_gate_a_roundtrip.jsx
 * GATE A - Illustrator execution verification round trip.
 *
 * Adobe Illustrator 2026, macOS.  File > Scripts > Other Script...
 *
 * What this script is and is not:
 *   - it automates Save As, close, reopen, PDF export, PNG export and the
 *     result JSON, so the owner does not do them by hand
 *   - it does NOT decide whether Gate A passes.  Only the two confirmation
 *     dialogs do that, and they are answered by a human looking at the screen
 *   - it never writes to the R2 source.  The source is opened and read; every
 *     output goes to a different filename, and that is asserted before saving
 *
 * It also records what Illustrator actually built - layer count, items per
 * layer, each item's name, z-index and bounds - on PASS as well as on FAIL.
 * R1 lost 37 objects and this environment cannot tell whether they were hidden
 * behind the body or never imported at all.  That diagnostic settles it.
 *
 * ASCII only, on purpose.
 */

#target illustrator

var SOURCE_NAME = "vq2_a2_r2_final_gate_a_r2.ai";
var VERIFIED_AI = "vq2_a2_r2_final_illustrator_verified.ai";
var VERIFIED_PDF = "vq2_a2_r2_final_illustrator_verified.pdf";
var VERIFIED_PNG = "vq2_a2_r2_final_illustrator_verified.png";
var RESULT_JSON = "illustrator_execution_verification_result.json";

var REQUIRED_GROUPS = [
    "01_STRUCTURE_BODY",
    "02_STRUCTURE_COLLAR",
    "03_STRUCTURE_CLOSURE",
    "04_APPROVED_BBROSE_LOGO",
    "05_DIVIDER",
    "06_ROSE_LETTERING",
    "07_DAMASCENA_LETTERING",
    "08_SUPPORTING_COPY"
];

var EXPECTED_OBJECTS = 40;

/* Illustrator counts PATH ITEMS, not logical drawings. A compound path is one
 * drawing and several path items, so these two numbers are different
 * inventories and can never be equal for this artwork. Comparing them is what
 * made a passing run record all_paths_arrived: false. The source has 40
 * drawings whose subpaths total 67, so 67 is the number to expect back. */
var EXPECTED_PATH_ITEMS = 67;

/* The R2 source page, and where the artwork sits inside it. The first round
 * trip preserved every object but saved onto a 763.654 x 983.225 artboard:
 * Illustrator's generic EPS import brings the artwork in without the source
 * page, and the script saved whatever default artboard it was given. The
 * artwork was translated, never resized, so the repair is to put the ORIGINAL
 * page back around it rather than to touch a single coordinate.
 *
 * The two margins below are Illustrator's own measurement of the source, so
 * they are on the same measurement basis as the bounds this script reads at
 * run time. Right and top are NOT applied as margins: the artboard is anchored
 * at left/bottom and then given the exact page size, so "width = 207.1627" is
 * true by construction and any sub-hundredth-of-a-point measurement difference
 * lands in the far margin where it changes nothing.
 */
var PAGE_W = 207.1627;
var PAGE_H = 493.2283;
var MARGIN_LEFT = 34.109999;
var MARGIN_BOTTOM = 34.001999;
var MARGIN_RIGHT_EXPECTED = 34.110565;
var MARGIN_TOP_EXPECTED = 35.218314;
var ARTBOARD_TOLERANCE = 0.001;

var QUESTIONS = [
    "Body, collar and closure colours are correct",
    "The BBROSE logo is visible",
    "The rose medallion and registered symbol are intact",
    "The divider rule is visible",
    "Rose and Damascena are visible",
    "NIGHT REPAIR OIL is visible",
    "Counters are open - H, both R, A, e, P are not filled in",
    "Objects are independently selectable and editable",
    "Illustrator showed NO warning or repair message"
];

/* ---------------------------------------------------------------- helpers */

function jsonEscape(s) {
    s = String(s);
    var out = "", i, c;
    for (i = 0; i < s.length; i++) {
        c = s.charAt(i);
        if (c === '"' || c === "\\") { out += "\\" + c; }
        else if (c === "\n") { out += "\\n"; }
        else if (c === "\r") { out += "\\r"; }
        else if (c === "\t") { out += "\\t"; }
        else if (c < " " || c > "~") { out += " "; }
        else { out += c; }
    }
    return out;
}

function toJson(v, indent) {
    var pad = "", i, parts, k;
    for (i = 0; i < indent; i++) { pad += " "; }
    if (v === null || v === undefined) { return "null"; }
    if (typeof v === "boolean") { return v ? "true" : "false"; }
    if (typeof v === "number") { return isFinite(v) ? String(v) : "null"; }
    if (v instanceof Array) {
        if (v.length === 0) { return "[]"; }
        parts = [];
        for (i = 0; i < v.length; i++) {
            parts.push(pad + " " + toJson(v[i], indent + 1));
        }
        return "[\n" + parts.join(",\n") + "\n" + pad + "]";
    }
    if (typeof v === "object") {
        parts = [];
        for (k in v) {
            if (v.hasOwnProperty(k)) {
                parts.push(pad + " \"" + jsonEscape(k) + "\": "
                           + toJson(v[k], indent + 1));
            }
        }
        if (parts.length === 0) { return "{}"; }
        return "{\n" + parts.join(",\n") + "\n" + pad + "}";
    }
    return "\"" + jsonEscape(v) + "\"";
}

function writeTextFile(file, text) {
    file.encoding = "UTF-8";
    file.lineFeed = "Unix";
    if (!file.open("w")) { return false; }
    file.write(text);
    file.close();
    return true;
}

function stamp() {
    var d = new Date();
    function p(n) { return (n < 10 ? "0" : "") + n; }
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate())
        + "T" + p(d.getHours()) + ":" + p(d.getMinutes()) + ":"
        + p(d.getSeconds());
}

/* Everything Illustrator actually built, recorded whatever the outcome.
 *
 * total_page_items counts only each layer's TOP-LEVEL items, so if Illustrator
 * wraps the whole import in one group it reads 1 while 40 paths are present.
 * path_items_total is document-wide and flattened, so "did all 40 paths
 * arrive" is answered however Illustrator chose to nest them - which is
 * exactly the question R1 raised.
 */
function inventory(doc) {
    var layers = [], i, j, lay, items, item, entry, bounds;
    var total = 0;
    for (i = 0; i < doc.layers.length; i++) {
        lay = doc.layers[i];
        items = lay.pageItems;
        entry = {
            "layer_index": i,
            "layer_name": lay.name,
            "visible": lay.visible,
            "locked": lay.locked,
            "item_count": items.length,
            "items": []
        };
        for (j = 0; j < items.length; j++) {
            item = items[j];
            bounds = null;
            try { bounds = [item.geometricBounds[0], item.geometricBounds[1],
                            item.geometricBounds[2], item.geometricBounds[3]]; }
            catch (eB) { bounds = null; }
            entry.items.push({
                "z_index": j,
                "name": item.name,
                "typename": item.typename,
                "hidden": item.hidden,
                "bounds": bounds
            });
            total++;
        }
        layers.push(entry);
    }
    var paths = 0, groups = 0, rasters = 0;
    try { paths = doc.pathItems.length; } catch (eP) { paths = -1; }
    try { groups = doc.groupItems.length; } catch (eG) { groups = -1; }
    try { rasters = doc.rasterItems.length; } catch (eR) { rasters = -1; }
    return { "layer_count": doc.layers.length, "layers": layers,
             "total_page_items": total, "path_items_total": paths,
             "group_items_total": groups, "raster_items_total": rasters };
}

/* R2 is plain EPS. Illustrator's EPS import discards DSC comments, so the
 * eight group names live in the FILE and will NOT come back as Illustrator
 * layer or object names - it will most likely build one layer of unnamed
 * paths. Their absence is expected and is not a finding. What matters is that
 * the paths arrived and that the artwork is visible, so the count is reported
 * against path_items_total and the judgement is left to the human's eyes.
 */
function groupNameReport(inv) {
    var found = [], missing = [], i, j, k, hay = "";
    for (i = 0; i < inv.layers.length; i++) {
        hay += "|" + inv.layers[i].layer_name;
        for (j = 0; j < inv.layers[i].items.length; j++) {
            hay += "|" + inv.layers[i].items[j].name;
        }
    }
    for (k = 0; k < REQUIRED_GROUPS.length; k++) {
        if (hay.indexOf(REQUIRED_GROUPS[k]) >= 0) {
            found.push(REQUIRED_GROUPS[k]);
        } else {
            missing.push(REQUIRED_GROUPS[k]);
        }
    }
    return {
        "expected_in_file_not_in_illustrator": REQUIRED_GROUPS,
        "found_as_illustrator_names": found,
        "absent_as_illustrator_names": missing,
        "absence_is_expected_for_eps": true,
        "absence_is_a_failure": false,
        "note": "group names are carried as DSC comments in the source and are "
                + "dropped by EPS import. Presence of the ARTWORK is judged by "
                + "path_items_total and by the human, not by these names."
    };
}

/* A checklist the human answers. Nothing is pre-ticked. */
function askDialog(titleText, introText, inv) {
    var dlg = new Window("dialog", titleText);
    var boxes = [], i;
    dlg.alignChildren = "left";
    dlg.add("statictext", undefined, introText, { multiline: true })
        .preferredSize = [520, 46];

    var stats = dlg.add("statictext", undefined,
        "Illustrator built " + inv.layer_count + " layer(s) and "
        + inv.path_items_total + " path item(s). Expected "
        + EXPECTED_PATH_ITEMS + " path items for " + EXPECTED_OBJECTS
        + " logical drawings - a compound path is one drawing and several "
        + "items, so those two numbers differ by design."
        + " A single unnamed layer is EXPECTED here - this is an EPS, so the "
        + "eight group names live in the file and do not come back as "
        + "Illustrator layer names. That is not a fault. What matters is the "
        + "path count above and what you can see.", { multiline: true });
    stats.preferredSize = [520, 62];

    var panel = dlg.add("panel", undefined, "Confirm every line you can see");
    panel.alignChildren = "left";
    panel.margins = 14;
    for (i = 0; i < QUESTIONS.length; i++) {
        boxes.push(panel.add("checkbox", undefined, QUESTIONS[i]));
    }

    var note = dlg.add("statictext", undefined,
        "Leave anything unticked that you cannot see or are unsure of. "
        + "Any unticked line records FAIL and no verified file is written.",
        { multiline: true });
    note.preferredSize = [520, 32];

    var row = dlg.add("group");
    var okBtn = row.add("button", undefined, "Confirm", { name: "ok" });
    var failBtn = row.add("button", undefined, "Report failure",
                          { name: "cancel" });
    var answers = null;

    okBtn.onClick = function () {
        answers = [];
        for (var n = 0; n < boxes.length; n++) { answers.push(boxes[n].value); }
        dlg.close(1);
    };
    failBtn.onClick = function () {
        answers = [];
        for (var n = 0; n < boxes.length; n++) { answers.push(boxes[n].value); }
        dlg.close(0);
    };
    dlg.show();

    var results = {}, allTrue = true;
    if (answers === null) { answers = []; }
    for (i = 0; i < QUESTIONS.length; i++) {
        var v = (i < answers.length) ? answers[i] : false;
        results[QUESTIONS[i]] = v;
        if (!v) { allTrue = false; }
    }
    return { "answers": results, "all_confirmed": allTrue };
}

/* A second run must not destroy the first run's record. That already happened
 * once: an aborted run overwrote the result of the run that produced the
 * verification copy, so the copy on disk had no provenance to point at. */
function writeResult(folder, rec) {
    var f = new File(folder.fsName + "/" + RESULT_JSON);
    if (f.exists) {
        var n = 1, keep;
        do {
            keep = new File(folder.fsName + "/"
                            + RESULT_JSON.replace(".json", "")
                            + "_previous_" + n + ".json");
            n++;
        } while (keep.exists && n < 100);
        try { f.copy(keep.fsName); } catch (eCopy) {
            rec.notes.push("could not preserve the previous result: " + eCopy);
        }
    }
    writeTextFile(f, toJson(rec, 0) + "\n");
    return f.fsName;
}

/* Union of every visible item, in Illustrator's [left, top, right, bottom]
 * convention where top > bottom. */
function unionBounds(doc) {
    var i, b, L = null, T = null, R = null, B = null;
    for (i = 0; i < doc.pageItems.length; i++) {
        if (doc.pageItems[i].hidden) { continue; }
        try { b = doc.pageItems[i].geometricBounds; } catch (e) { continue; }
        if (L === null || b[0] < L) { L = b[0]; }
        if (T === null || b[1] > T) { T = b[1]; }
        if (R === null || b[2] > R) { R = b[2]; }
        if (B === null || b[3] < B) { B = b[3]; }
    }
    if (L === null) { return null; }
    return [L, T, R, B];
}

/* Put the source page back around the artwork. Nothing is moved or scaled. */
function restoreArtboard(doc) {
    var u = unionBounds(doc);
    var rec = {
        "attempted": true,
        "union_bounds": u,
        "target_page_pt": [PAGE_W, PAGE_H],
        "artwork_translated": false,
        "artwork_rescaled": false,
        "artboards_before": doc.artboards.length,
        "applied": false
    };
    if (u === null) { rec.error = "no visible page items"; return rec; }

    var left = u[0] - MARGIN_LEFT;
    var bottom = u[3] - MARGIN_BOTTOM;
    var right = left + PAGE_W;
    var top = bottom + PAGE_H;

    /* extra artboards would make the exports ambiguous */
    while (doc.artboards.length > 1) {
        try { doc.artboards.remove(doc.artboards.length - 1); }
        catch (eRem) { break; }
    }
    try {
        doc.artboards[0].artboardRect = [left, top, right, bottom];
        rec.applied = true;
    } catch (eSet) {
        rec.error = "could not set artboardRect: " + eSet;
        return rec;
    }

    var r = doc.artboards[0].artboardRect;
    rec.artboard_rect = [r[0], r[1], r[2], r[3]];
    rec.width_pt = r[2] - r[0];
    rec.height_pt = r[3] - r[1];
    if (rec.height_pt < 0) { rec.height_pt = r[1] - r[3]; }
    rec.achieved_margins = {
        "left": u[0] - r[0],
        "bottom": u[3] - (r[1] < r[3] ? r[1] : r[3]),
        "right": r[2] - u[2],
        "top": (r[1] > r[3] ? r[1] : r[3]) - u[1]
    };
    rec.expected_margins = {
        "left": MARGIN_LEFT, "bottom": MARGIN_BOTTOM,
        "right": MARGIN_RIGHT_EXPECTED, "top": MARGIN_TOP_EXPECTED
    };
    rec.width_ok = Math.abs(rec.width_pt - PAGE_W) <= ARTBOARD_TOLERANCE;
    rec.height_ok = Math.abs(rec.height_pt - PAGE_H) <= ARTBOARD_TOLERANCE;
    rec.passed = (rec.applied && rec.width_ok && rec.height_ok);
    rec.artboards_after = doc.artboards.length;
    return rec;
}

function artboardSize(doc) {
    var r = doc.artboards[0].artboardRect;
    var w = r[2] - r[0];
    var h = (r[1] > r[3]) ? (r[1] - r[3]) : (r[3] - r[1]);
    return {"width_pt": w, "height_pt": h,
            "width_ok": Math.abs(w - PAGE_W) <= ARTBOARD_TOLERANCE,
            "height_ok": Math.abs(h - PAGE_H) <= ARTBOARD_TOLERANCE};
}

/* ------------------------------------------------------------------- main */

function main() {
    var src = File.openDialog("Select " + SOURCE_NAME, "*.ai", false);
    if (src === null) { return; }

    var folder = src.parent;
    /* captured BEFORE the file is opened; comparing src.length to a fresh
       File on the same path afterwards would compare the file with itself and
       always be true */
    var srcSizeBefore = src.length;
    var rec = {
        "record_type": "illustrator_execution_verification_result/1.0",
        "produced_by": "illustrator_gate_a_roundtrip.jsx",
        "authorship": {
            "source_file": "CLAUDE_GENERATED_SOURCE",
            "round_trip": "ILLUSTRATOR_SCRIPT_AUTOMATED_ROUNDTRIP",
            "visual_judgement": "HUMAN_VISUAL_CONFIRMATION"
        },
        "claude_operated_illustrator": false,
        "illustrator_version": String(app.version),
        "application": String(app.name),
        "operating_system": String($.os),
        "performed_at": stamp(),
        "source_filename": src.name,
        "source_path": src.fsName,
        "verified_filename": null,
        "expected_groups": REQUIRED_GROUPS,
        "expected_object_count": EXPECTED_OBJECTS,
        "group_inventory": null,
        "object_count": null,
        "opened_inventory": null,
        "reopened_inventory": null,
        "first_confirmation": null,
        "second_confirmation": null,
        "warning_state": null,
        "expected_page_pt": [PAGE_W, PAGE_H],
        "artboard_restore": null,
        "artboard_after_reopen": null,
        "save_completed": false,
        "reopen_completed": false,
        "pdf_export_completed": false,
        "png_export_completed": false,
        "source_unmodified": true,
        "human_result": "FAIL",
        "notes": []
    };

    if (src.name !== SOURCE_NAME) {
        /* the first run selected this script itself in the file dialog and
           the old code continued into a failed open, producing a FAIL record
           about the wrong file. A wrong subject is not something to carry on
           from. */
        rec.notes.push("Selected file is " + src.name + ", expected "
                       + SOURCE_NAME + ". Stopped without opening anything.");
        rec.warning_state = "WRONG_FILE_SELECTED";
        writeResult(folder, rec);
        alert("That is not " + SOURCE_NAME + ".\n\nYou selected: " + src.name
              + "\n\nNothing was opened and nothing was written except the "
              + "FAIL record. Run the script again and choose the .ai file.");
        return;
    }

    var doc = null;
    try {
        doc = app.open(src);
    } catch (eOpen) {
        rec.notes.push("Illustrator could not open the file: " + eOpen);
        rec.warning_state = "OPEN_FAILED";
        writeResult(folder, rec);
        alert("Illustrator could not open the file. FAIL recorded.");
        return;
    }

    var inv = inventory(doc);
    rec.opened_inventory = inv;
    rec.object_count = inv.path_items_total;
    rec.group_inventory = groupNameReport(inv);
    rec.path_items_expected = EXPECTED_PATH_ITEMS;
    rec.all_path_items_arrived =
        (inv.path_items_total === EXPECTED_PATH_ITEMS);
    rec.all_logical_objects_arrived = rec.all_path_items_arrived;
    rec.counting_note = "logical drawings (" + EXPECTED_OBJECTS + ") and "
        + "Illustrator path items (" + EXPECTED_PATH_ITEMS + ") are different "
        + "inventories; a compound path is one drawing and several items.";

    var first = askDialog(
        "Gate A - verify the opened file",
        "This is " + src.name + " as Illustrator has just built it. Tick only "
        + "what you can actually see on screen. This is the check R1 failed: "
        + "it opened with the three structure objects and none of the artwork.",
        inv);
    rec.first_confirmation = first.answers;
    rec.warning_state = first.answers[QUESTIONS[8]] ? "NONE_REPORTED"
                                                    : "WARNING_OR_UNCONFIRMED";

    if (!first.all_confirmed) {
        rec.notes.push("First confirmation incomplete - no verified file was "
                       + "written and Gate A remains blocked.");
        doc.close(SaveOptions.DONOTSAVECHANGES);
        var p1 = writeResult(folder, rec);
        alert("FAIL recorded. The source was not modified and no verified "
              + "file was written.\n\n" + p1);
        return;
    }

    var aiOut = new File(folder.fsName + "/" + VERIFIED_AI);
    if (aiOut.fsName === src.fsName) {
        rec.notes.push("Refused to save: the target equals the source.");
        doc.close(SaveOptions.DONOTSAVECHANGES);
        writeResult(folder, rec);
        alert("Refused to overwrite the source. FAIL recorded.");
        return;
    }

    rec.artboard_restore = restoreArtboard(doc);
    if (!rec.artboard_restore.passed) {
        rec.notes.push("Artboard could not be restored to "
                       + PAGE_W + " x " + PAGE_H
                       + " pt; refusing to save a document whose page size "
                       + "does not match the accepted source.");
        rec.warning_state = "ARTBOARD_RESTORE_FAILED";
        doc.close(SaveOptions.DONOTSAVECHANGES);
        var pA = writeResult(folder, rec);
        alert("FAIL - the artboard could not be restored to the accepted page "
              + "size. Nothing was saved.\n\n" + pA);
        return;
    }

    try {
        var aiOpts = new IllustratorSaveOptions();
        aiOpts.compatibility = Compatibility.ILLUSTRATOR17;
        aiOpts.pdfCompatible = true;
        doc.saveAs(aiOut, aiOpts);
        rec.save_completed = true;
        rec.verified_filename = VERIFIED_AI;
    } catch (eSave) {
        rec.notes.push("Save As failed: " + eSave);
        doc.close(SaveOptions.DONOTSAVECHANGES);
        writeResult(folder, rec);
        alert("Save As failed. FAIL recorded.");
        return;
    }

    doc.close(SaveOptions.SAVECHANGES);

    var reopened = null;
    try {
        reopened = app.open(aiOut);
        rec.reopen_completed = true;
    } catch (eReopen) {
        rec.notes.push("Reopen failed: " + eReopen);
        writeResult(folder, rec);
        alert("Reopen failed. FAIL recorded.");
        return;
    }

    var inv2 = inventory(reopened);
    rec.reopened_inventory = inv2;
    rec.artboard_after_reopen = artboardSize(reopened);
    if (!rec.artboard_after_reopen.width_ok
            || !rec.artboard_after_reopen.height_ok) {
        rec.notes.push("The reopened copy's artboard is "
                       + rec.artboard_after_reopen.width_pt + " x "
                       + rec.artboard_after_reopen.height_pt
                       + " pt, not " + PAGE_W + " x " + PAGE_H + ".");
        rec.warning_state = "ARTBOARD_DRIFT_AFTER_REOPEN";
        reopened.close(SaveOptions.DONOTSAVECHANGES);
        var pB = writeResult(folder, rec);
        alert("FAIL - the artboard did not survive the round trip.\n\n" + pB);
        return;
    }

    var second = askDialog(
        "Gate A - verify the reopened verification copy",
        "This is " + VERIFIED_AI + " after saving, closing and reopening. "
        + "Confirm it still looks right. A file that survives the round trip "
        + "is what Gate A actually requires.",
        inv2);
    rec.second_confirmation = second.answers;

    if (!second.all_confirmed) {
        rec.notes.push("Second confirmation incomplete - the round trip did "
                       + "not survive. No PASS is recorded.");
        reopened.close(SaveOptions.DONOTSAVECHANGES);
        var p2 = writeResult(folder, rec);
        alert("FAIL recorded after reopen.\n\n" + p2);
        return;
    }

    try {
        var pngOpts = new ExportOptionsPNG24();
        pngOpts.artBoardClipping = true;
        pngOpts.horizontalScale = 300.0;
        pngOpts.verticalScale = 300.0;
        pngOpts.transparency = false;
        reopened.exportFile(new File(folder.fsName + "/" + VERIFIED_PNG),
                            ExportType.PNG24, pngOpts);
        rec.png_export_completed = true;
    } catch (ePng) {
        rec.notes.push("PNG export failed: " + ePng);
    }

    try {
        var pdfOpts = new PDFSaveOptions();
        pdfOpts.preserveEditability = true;
        pdfOpts.generateThumbnails = false;
        /* saveAs rebinds the open document to the PDF; the verified .ai is
           already written to disk, so the document is closed without saving. */
        reopened.saveAs(new File(folder.fsName + "/" + VERIFIED_PDF), pdfOpts);
        rec.pdf_export_completed = true;
    } catch (ePdf) {
        rec.notes.push("PDF export failed: " + ePdf);
    }

    try { reopened.close(SaveOptions.DONOTSAVECHANGES); } catch (eClose) {}

    rec.source_size_before = srcSizeBefore;
    rec.source_size_after = new File(src.fsName).length;
    rec.source_unmodified = (rec.source_size_after === srcSizeBefore);

    rec.human_result = (rec.save_completed && rec.reopen_completed
                        && rec.pdf_export_completed && rec.png_export_completed
                        && first.all_confirmed && second.all_confirmed
                        && rec.artboard_restore.passed
                        && rec.artboard_after_reopen.width_ok
                        && rec.artboard_after_reopen.height_ok)
        ? "PASS" : "FAIL";

    var path = writeResult(folder, rec);
    alert("Round trip complete.\n\nResult: " + rec.human_result
          + "\n\nWritten:\n" + VERIFIED_AI + "\n" + VERIFIED_PDF + "\n"
          + VERIFIED_PNG + "\n" + RESULT_JSON
          + "\n\nGate A is not passed until this result is returned to the "
          + "repository and its checks are recorded.\n\n" + path);
}

main();
