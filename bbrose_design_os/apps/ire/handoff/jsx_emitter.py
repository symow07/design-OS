"""design_handoff.jsx emitter (Phase 2A-8 §2/§3/§13).

Generates a deterministic, data-driven ExtendScript: the serialized
illustrator_handoff_graph/1.0 is embedded as a PLAIN OBJECT LITERAL (JSON is
valid ES3 literal syntax — no eval, no JSON polyfill) followed by a fixed,
bounded runtime that reconstructs the native document: named layers in the
mandated order, panel sublayers, semantic groups, Bézier paths, live point
text in the exact requested faces (missing face → ILLUSTRATOR_FONT_MISSING,
never a silent substitute, never auto-outlining), registered process and
spot swatches, editable gradients, clipping masks, opacity, printability
and locking.

Script safety (§13): no eval, no network objects, no shell, no arbitrary
file traversal — the only filesystem touch is an optional linked-asset
lookup inside the ``assets/`` folder NEXT TO the script, and the script
never writes or saves anything; the designer saves the document.
"""
from __future__ import annotations

import json

from apps.ire.handoff.graph_schema import HANDOFF_SCHEMA

EMITTER_VERSION = "jsx_emitter/1.0"

_RUNTIME = r"""
// ---- fixed bounded runtime (no eval, no network, no writes) ----------------
var MM = 2.834645669291339;   // mm -> pt

function cmyk(values) {
    var c = new CMYKColor();
    c.cyan = values[0] * 100; c.magenta = values[1] * 100;
    c.yellow = values[2] * 100; c.black = values[3] * 100;
    return c;
}

var report = {missingFonts: [], missingAssets: [], textFrames: 0,
              pathItems: 0, rasters: 0, layers: 0, groups: 0,
              spots: 0, swatches: 0, errors: []};

// suppress modal dialogs during automated execution (restored at the end)
var _previousInteraction = null;
try {
    _previousInteraction = app.userInteractionLevel;
    app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
} catch (e) {}

// ---- §1 ATOMIC font preflight: resolve EVERY required face BEFORE any
// document exists. Missing → abort with HANDOFF_FONT_UNAVAILABLE; no
// partial document, no substitution, no outlining.
var _missing = [];
for (var f = 0; f < HANDOFF.fonts.length; f++) {
    try { app.textFonts.getByName(HANDOFF.fonts[f]); }
    catch (fontErr) { _missing.push(HANDOFF.fonts[f]); }
}
if (_missing.length > 0) {
    try {
        if (_previousInteraction !== null) {
            app.userInteractionLevel = _previousInteraction;
        }
    } catch (e) {}
    var parts = [];
    for (var q = 0; q < _missing.length; q++) {
        parts.push('"' + _missing[q] + '"');
    }
    '{"status":"HANDOFF_FONT_UNAVAILABLE","missingFonts":['
        + parts.join(",") + "]}";
} else {

var doc = app.documents.add(
    DocumentColorSpace.CMYK,
    HANDOFF.artboard.w_mm * MM, HANDOFF.artboard.h_mm * MM);
try { app.coordinateSystem = CoordinateSystem.ARTBOARDCOORDINATESYSTEM; }
catch (e) {}

// ---- §2 THE canonical transform: every object type goes through PT/LEN.
// Graph space: mm, y-down, origin top-left. Illustrator artboard space:
// points, y NEGATIVE downward from the artboard's top-left.
function PT(x_mm, y_mm) { return [x_mm * MM, -y_mm * MM]; }
function LEN(v_mm) { return v_mm * MM; }
function X(x_mm) { return PT(x_mm, 0)[0]; }
function Y(y_mm) { return PT(0, y_mm)[1]; }

// ---- swatches ---------------------------------------------------------------
var processColors = {};
var i, s;
for (i = 0; i < HANDOFF.process_swatches.length; i++) {
    s = HANDOFF.process_swatches[i];
    var sw;
    try { sw = doc.swatches.getByName(s.name); }
    catch (e) {
        sw = doc.swatches.add();
        sw.name = s.name;
        sw.color = cmyk(s.cmyk);
    }
    processColors[s.name] = cmyk(s.cmyk);
    report.swatches++;
}
var spotColors = {};
for (i = 0; i < HANDOFF.spot_swatches.length; i++) {
    s = HANDOFF.spot_swatches[i];
    var spot;
    try { spot = doc.spots.getByName(s.name); }
    catch (e) {
        spot = doc.spots.add();
        spot.name = s.name;
        spot.colorType = ColorModel.SPOT;
        spot.color = cmyk(s.cmyk);
    }
    var sc = new SpotColor();
    sc.spot = spot; sc.tint = 100;
    spotColors[s.name] = sc;
    report.spots++;
}
function colorFor(name) {
    if (spotColors[name]) return spotColors[name];
    if (processColors[name]) return processColors[name];
    return cmyk([0, 0, 0, 1]);
}

// ---- layers (create bottom-up so index 0 of ROOT_LAYERS ends on top) --------
var layerByName = {};
for (i = HANDOFF.root_layers.length - 1; i >= 0; i--) {
    var layer = doc.layers.add();
    layer.name = HANDOFF.root_layers[i];
    layerByName[layer.name] = layer;
    report.layers++;
}
// default "Layer 1" from documents.add — remove if empty
try {
    var first = doc.layers.getByName("Layer 1");
    if (first.pageItems.length === 0) { first.remove(); }
} catch (e) {}

// panel/surface sublayers: data-driven map {layer: [names]} (2B-4B);
// packaging graphs without the map keep the legacy 05_PANEL_ARTWORK tree.
var panelMap = HANDOFF.panel_sublayer_map ||
    {"05_PANEL_ARTWORK": HANDOFF.panel_sublayers};
var panelSublayers = {};
for (var parentName in panelMap) {
    if (!layerByName[parentName]) { continue; }
    var subNames = panelMap[parentName] || [];
    panelSublayers[parentName] = {};
    for (i = subNames.length - 1; i >= 0; i--) {
        var sub = layerByName[parentName].layers.add();
        sub.name = subNames[i];
        panelSublayers[parentName][sub.name] = sub;
    }
}

// non-printing layers
for (i = 0; i < HANDOFF.non_printing_layers.length; i++) {
    try { layerByName[HANDOFF.non_printing_layers[i]].printable = false; }
    catch (e) {}
}

// ---- group containers -------------------------------------------------------
var groupCache = {};
function containerFor(obj) {
    var host = layerByName[obj.layer];
    if (obj.panel && panelSublayers[obj.layer] &&
            panelSublayers[obj.layer][obj.panel]) {
        host = panelSublayers[obj.layer][obj.panel];
    }
    var path = obj.group_path || [];
    var key = obj.layer + "|" + (obj.panel || "") ;
    var parent = host;
    for (var g = 0; g < path.length; g++) {
        // panel sublayer name may repeat as the first path element
        if (g === 0 && path[g] === obj.panel) { continue; }
        key += "/" + path[g];
        if (!groupCache[key]) {
            var grp = parent.groupItems.add();
            grp.name = path[g];
            groupCache[key] = grp;
            report.groups++;
        }
        parent = groupCache[key];
    }
    return parent;
}

// ---- geometry ---------------------------------------------------------------
function drawSubpath(container, points, closed, obj) {
    var p = container.pathItems.add();
    p.name = obj.name;
    p.closed = closed;
    p.setEntirePath([[points[0].a[0], points[0].a[1]]]);
    // rebuild with full anchors + handles
    while (p.pathPoints.length < points.length) { p.pathPoints.add(); }
    for (var k = 0; k < points.length; k++) {
        var pp = p.pathPoints[k];
        pp.anchor = points[k].a;
        pp.leftDirection = points[k].l || points[k].a;
        pp.rightDirection = points[k].r || points[k].a;
        // straight joints stay CORNER — forcing SMOOTH distorted rects,
        // frames and dieline geometry (2A-8-CORR-1 §2)
        pp.pointType = (points[k].l || points[k].r)
            ? PointType.SMOOTH : PointType.CORNER;
    }
    return p;
}

function buildPaths(container, obj) {
    var subs = [], pts = [], cur = null, closed = false;
    var segs = obj.segments || [];
    for (var k = 0; k < segs.length; k++) {
        var seg = segs[k];
        if (seg[0] === "M") {
            if (pts.length) { subs.push({pts: pts, closed: closed}); }
            pts = [{a: [X(seg[1]), Y(seg[2])]}]; closed = false;
        } else if (seg[0] === "L") {
            pts.push({a: [X(seg[1]), Y(seg[2])]});
        } else if (seg[0] === "C") {
            if (pts.length) {
                pts[pts.length - 1].r = [X(seg[1]), Y(seg[2])];
            }
            pts.push({a: [X(seg[5]), Y(seg[6])],
                      l: [X(seg[3]), Y(seg[4])]});
        } else if (seg[0] === "Z") {
            closed = true;
        }
    }
    if (pts.length) { subs.push({pts: pts, closed: closed}); }
    var items = [];
    for (var m = 0; m < subs.length; m++) {
        items.push(drawSubpath(container, subs[m].pts, subs[m].closed, obj));
    }
    return items;
}

function applyPaint(items, obj) {
    for (var k = 0; k < items.length; k++) {
        var it = items[k];
        var nodeOpacity = (obj.opacity === undefined ? 1 : obj.opacity);
        if (obj.fill && obj.fill.type === "solid") {
            it.filled = true;
            it.fillColor = colorFor(obj.fill.swatch);
            it.opacity = nodeOpacity * (obj.fill.opacity || 1) * 100;
        } else if (obj.fill && obj.fill.type === "gradient") {
            var grad;
            try { grad = doc.gradients.getByName(obj.name + "-gradient"); }
            catch (e) {
                grad = doc.gradients.add();
                grad.name = obj.name + "-gradient";
                grad.type = (obj.fill.kind === "radial")
                    ? GradientType.RADIAL : GradientType.LINEAR;
                while (grad.gradientStops.length < obj.fill.stops.length) {
                    grad.gradientStops.add();
                }
                for (var t = 0; t < obj.fill.stops.length; t++) {
                    var stop = grad.gradientStops[t];
                    stop.rampPoint = obj.fill.stops[t].offset * 100;
                    stop.color = processColors[obj.fill.stops[t].swatch]
                        || cmyk([0, 0, 0, 0]);
                }
            }
            var gc = new GradientColor();
            gc.gradient = grad;
            it.filled = true;
            it.fillColor = gc;
            // GradientColor.angle is NOT honored on assignment (verified
            // against Illustrator 2026: the ramp always renders at 0°
            // across the item). Rotate the FILL GRADIENT ONLY afterwards —
            // the reliable idiom. Angle in Illustrator's y-up convention.
            var angleDeg = Math.atan2(
                -(obj.fill.y2 - obj.fill.y1),
                (obj.fill.x2 - obj.fill.x1)) * 180 / Math.PI;
            if (angleDeg !== 0) {
                it.rotate(angleDeg, false, false, true, false,
                          Transformation.CENTER);
            }
            it.opacity = nodeOpacity * 100;   // the mint wash is ATMOSPHERIC
        } else {
            it.filled = false;
        }
        if (obj.stroke) {
            it.stroked = true;
            it.strokeColor = colorFor(obj.stroke.swatch);
            it.strokeWidth = obj.stroke.width_mm * MM;
            if (obj.stroke.dash) { it.strokeDashes = obj.stroke.dash; }
            if (!obj.fill) {
                it.opacity = nodeOpacity * (obj.stroke.opacity || 1) * 100;
            }
        } else {
            it.stroked = false;
        }
        report.pathItems++;
    }
}

// ---- objects ----------------------------------------------------------------
var obj;
for (i = 0; i < HANDOFF.objects.length; i++) {
    obj = HANDOFF.objects[i];
    var container = containerFor(obj);
    try {
        if (obj.type === "path") {
            applyPaint(buildPaths(container, obj), obj);
        } else if (obj.type === "rect") {
            var rect = container.pathItems.rectangle(
                Y(obj.y), X(obj.x), obj.w * MM, obj.h * MM);
            rect.name = obj.name;
            applyPaint([rect], obj);
            report.pathItems--;   // applyPaint counted it; census counts rects
            report.pathItems++;
        } else if (obj.type === "text") {
            var _step = "pointText";
            var tf = container.textFrames.pointText(
                [X(obj.x), Y(obj.y)]);
            _step = "name";
            tf.name = obj.name;
            _step = "contents";
            tf.contents = obj.text;
            _step = "getAttrs";
            var attrs = tf.textRange.characterAttributes;
            _step = "size";
            attrs.size = obj.size_pt;
            _step = "fillColor";
            attrs.fillColor = colorFor(obj.swatch);
            _step = "post-fill";
            try {
                attrs.textFont = app.textFonts.getByName(obj.font_postscript);
            } catch (fontError) {
                report.missingFonts.push(obj.font_postscript);
            }
            if (obj.align === "center") {
                tf.textRange.paragraphAttributes.justification =
                    Justification.CENTER;
            } else if (obj.align === "right") {
                tf.textRange.paragraphAttributes.justification =
                    Justification.RIGHT;
            }
            if (obj.rotation_deg) {
                // rotate about the TEXT ANCHOR, matching the PDF emitter:
                // rotate about center, then translate the anchor back
                var anchor = PT(obj.x, obj.y);
                var gb = tf.geometricBounds;   // [left, top, right, bottom]
                var cx = (gb[0] + gb[2]) / 2, cy = (gb[1] + gb[3]) / 2;
                tf.rotate(obj.rotation_deg);
                var rad = obj.rotation_deg * Math.PI / 180;
                var ax = anchor[0] - cx, ay = anchor[1] - cy;
                var rx = cx + ax * Math.cos(rad) - ay * Math.sin(rad);
                var ry = cy + ax * Math.sin(rad) + ay * Math.cos(rad);
                tf.translate(anchor[0] - rx, anchor[1] - ry);
            }
            report.textFrames++;
        } else if (obj.type === "image") {
            // bounded linked-asset lookup: ONLY ./assets next to the script
            var assetsFolder = File($.fileName).parent.fsName + "/assets/";
            var assetFile = new File(assetsFolder + obj.linked_asset);
            if (assetFile.exists) {
                var placed = container.placedItems.add();
                placed.file = assetFile;
                placed.name = obj.name;
                placed.position = [X(obj.x), Y(obj.y)];
                placed.width = obj.w * MM;
                placed.height = obj.h * MM;
                report.rasters++;
            } else {
                report.missingAssets.push(obj.linked_asset);
            }
        } else if (obj.type === "sticker_bridge") {
            var note = container.textFrames.pointText(
                [X(obj.x), Y(obj.y)]);
            note.name = obj.name;
            note.contents = "[regulatory sticker zone " + obj.w + "x"
                + obj.h + " mm — see preview PDF; native port pending]";
            note.textRange.characterAttributes.size = 6;
            report.textFrames++;
        }
    } catch (objError) {
        report.errors.push(obj.id + "@" + (typeof _step === "undefined"
            ? "?" : _step) + ": " + objError);
    }
}

// ---- §4 panel clipping masks (the clip path must be the TOP item of a
// clipped group; items added later sit in front, so add the clip last)
for (i = 0; i < (HANDOFF.panel_clips || []).length; i++) {
    var clipSpec = HANDOFF.panel_clips[i];
    try {
        var clipContainer = containerFor(clipSpec);
        var clipItems = buildPaths(clipContainer,
            {name: "panel-clip", segments: clipSpec.segments});
        for (var cp = 0; cp < clipItems.length; cp++) {
            clipItems[cp].filled = false;
            clipItems[cp].stroked = false;
            clipItems[cp].clipping = true;
        }
        clipContainer.clipped = true;
    } catch (clipErr) {
        report.errors.push("clip " + clipSpec.panel + ": " + clipErr);
    }
}

// ---- §6 design-review visibility: technical + finish layers ship hidden
// (named, selectable, preserved — toggle on for the prepress state)
for (i = 0; i < (HANDOFF.default_hidden_layers || []).length; i++) {
    try {
        layerByName[HANDOFF.default_hidden_layers[i]].visible = false;
    } catch (e) {}
}

// ---- lock technical layers --------------------------------------------------
try { layerByName["01_DIELINE_CUT"].locked = true; } catch (e) {}
try { layerByName["02_DIELINE_FOLD"].locked = true; } catch (e) {}

/*__VERIFICATION_BLOCK__*/

// ---- bounded summary (manual serialization — no JSON dependency) ------------
function j(text) {
    return '"' + String(text).replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"') + '"';
}
function jlist(values) {
    var parts = [];
    for (var q = 0; q < values.length; q++) { parts.push(j(values[q])); }
    return "[" + parts.join(",") + "]";
}
var summary = "{" +
    '"layers":' + report.layers + "," +
    '"groups":' + report.groups + "," +
    '"textFrames":' + report.textFrames + "," +
    '"pathItems":' + report.pathItems + "," +
    '"rasters":' + report.rasters + "," +
    '"swatches":' + report.swatches + "," +
    '"spots":' + report.spots + "," +
    '"missingFonts":' + jlist(report.missingFonts) + "," +
    '"missingAssets":' + jlist(report.missingAssets) + "," +
    '"errors":' + jlist(report.errors) +
    "}";
try {
    if (_previousInteraction !== null) {
        app.userInteractionLevel = _previousInteraction;
    }
} catch (e) {}
summary = summary.replace("}", ',"status":"OK"}');
summary;
}   // end font-preflight else
"""


_VERIFICATION_BLOCK = r"""
// ---- §9 verification mode: export PDF + PNG next to this script, then
// close the diagnostic document WITHOUT saving. Writes are bounded to the
// script's own folder; the designer-facing design_handoff.jsx never writes.
var _outFolder = File($.fileName).parent.fsName;
try {
    var pdfOptions = new PDFSaveOptions();
    pdfOptions.preserveEditability = false;
    doc.saveAs(new File(_outFolder + "/illustrator_exported_preview.pdf"),
               pdfOptions);
} catch (exportErr) { report.errors.push("pdf-export: " + exportErr); }
try {
    var pngOptions = new ExportOptionsPNG24();
    pngOptions.artBoardClipping = true;
    pngOptions.horizontalScale = 100; pngOptions.verticalScale = 100;
    doc.exportFile(new File(_outFolder + "/illustrator_exported_preview.png"),
                   ExportType.PNG24, pngOptions);
} catch (pngErr) { report.errors.push("png-export: " + pngErr); }
try { doc.close(SaveOptions.DONOTSAVECHANGES); }
catch (closeErr) { report.errors.push("close: " + closeErr); }
"""


#: THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
#: switch the mark to it so gold foil can print." `buildPaths` above draws EVERY subpath of a path as its own item —
#: right for a rule or a frame, wrong for the house mark drawn from its approved vector master: the counters of B, R
#: and O are subpaths, and drawn as items of their own they fill black. A path that declares its fill rule (only that
#: mark does) is drawn as ONE compound path, every subpath an item of it, so an inner outline cuts its hole by the rule
#: the PDF draws it with; its paint goes on the compound's paths (Illustrator gives a compound one appearance) and its
#: opacity on the compound. INJECTED ONLY into a script whose graph carries such a path: every other script is the
#: runtime above, byte for byte, and no manifest's jsx_hash moves.
_COMPOUND_HELPERS_ANCHOR = (
    "// ---- objects ----------------------------------------------------------------\n")
_COMPOUND_HELPERS = r"""// ---- compound paths (the owner's second answer of 2026-09-25): the house mark drawn from its approved vector
// master declares its fill rule and is ONE compound path, so its counters stay holes
function buildCompound(container, obj) {
    var cp = container.compoundPathItems.add();
    cp.name = obj.name;
    buildPaths(cp, obj);
    return cp;
}

function applyCompound(cp, obj) {
    var nodeOpacity = (obj.opacity === undefined ? 1 : obj.opacity);
    for (var k = 0; k < cp.pathItems.length; k++) {
        var it = cp.pathItems[k];
        if (obj.fill && obj.fill.type === "solid") {
            it.filled = true;
            it.fillColor = colorFor(obj.fill.swatch);
        } else {
            it.filled = false;
        }
        it.stroked = false;
        it.evenodd = (obj.fill_rule === "evenodd");
        report.pathItems++;
    }
    cp.opacity = nodeOpacity * ((obj.fill && obj.fill.opacity) || 1) * 100;
}

"""
_COMPOUND_BRANCH_ANCHOR = (
    '        if (obj.type === "path") {\n'
    '            applyPaint(buildPaths(container, obj), obj);\n')
_COMPOUND_BRANCH = (
    '        if (obj.type === "path" && obj.fill_rule) {\n'
    '            applyCompound(buildCompound(container, obj), obj);\n'
    '        } else if (obj.type === "path") {\n'
    '            applyPaint(buildPaths(container, obj), obj);\n')


def _with_compound_paths(runtime: str) -> str:
    """The runtime with the compound-path helpers and branch in it. Each anchor must be in the runtime exactly once —
    a runtime that moved under this raises, by name, rather than ship a script that draws the mark's counters black."""
    for anchor in (_COMPOUND_HELPERS_ANCHOR, _COMPOUND_BRANCH_ANCHOR):
        if runtime.count(anchor) != 1:
            raise ValueError("HANDOFF_COMPOUND_ANCHOR_MOVED: %r is in the runtime %d times"
                             % (anchor.strip(), runtime.count(anchor)))
    runtime = runtime.replace(_COMPOUND_HELPERS_ANCHOR, _COMPOUND_HELPERS + _COMPOUND_HELPERS_ANCHOR)
    return runtime.replace(_COMPOUND_BRANCH_ANCHOR, _COMPOUND_BRANCH)


def emit_design_handoff_jsx(graph: dict, *, verification: bool = False) -> str:
    """The deterministic design_handoff.jsx for a serialized graph."""
    if graph.get("schema_version") not in (
            HANDOFF_SCHEMA, "container_illustrator_handoff_graph/1.0"):
        raise ValueError("unsupported handoff graph schema")
    data_literal = json.dumps(graph, ensure_ascii=True, indent=None,
                              separators=(",", ":"))
    header = (
        "// BBROSE Design OS — native Illustrator handoff\n"
        f"// schema {HANDOFF_SCHEMA} · emitter {EMITTER_VERSION}\n"
        f"// task {graph.get('task_id')} · Design Graph is the source of "
        "truth; this script is an execution format.\n"
        "// Finish layers are SPOT production masks — final overprint and\n"
        "// separation settings require prepress review.\n"
        "// Safety: data-driven; no eval, no network, no writes; assets are\n"
        "// resolved ONLY from ./assets next to this script.\n"
    )
    runtime = _RUNTIME.replace(
        "/*__VERIFICATION_BLOCK__*/",
        _VERIFICATION_BLOCK if verification else "")
    # [the owner's second answer of 2026-09-25: compound paths, only for a graph that carries a declared fill rule]
    if any(obj.get("fill_rule") for obj in graph.get("objects") or ()):
        runtime = _with_compound_paths(runtime)
    return header + "var HANDOFF = " + data_literal + ";\n" + runtime


__all__ = ["emit_design_handoff_jsx", "EMITTER_VERSION"]
