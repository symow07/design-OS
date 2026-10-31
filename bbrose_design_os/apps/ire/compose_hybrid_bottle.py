"""Deterministic artwork from DesignSpec. No image interpretation or tracing."""
from __future__ import annotations

import base64
import copy
import xml.etree.ElementTree as ET

from fontTools.ttLib import TTFont
from reportlab.pdfbase import pdfmetrics

from apps.ire.graph import AssetRef, Color, Document, Group, Image, Rect, SolidFill, TextRun
from apps.pipeline.services.design_spec import digest, resolve_assets, resolve_fonts


def compose(spec):
    paths, ppi = resolve_assets(spec)
    fonts = resolve_fonts(spec.type_tokens)
    tokens = {t.role: t for t in spec.type_tokens}
    width, height, margin = spec.surface.width_mm, spec.surface.height_mm, spec.surface.safe_mm
    ink = Color.from_hex(spec.palette.secondary)
    layout, front, back = [], [], []

    def line(text, role, baseline, *, surface="body.front", maximum=21.0, x=5.5, copy_id=None):
        from apps.dielines.exporters.text_intl import shape_ar
        from apps.ire.estimated_sign import width as sign_width
        token, face = tokens[role], fonts[role]
        shown = shape_ar(text, keep_harakat=True) if role == "arabic" else text
        advance = sign_width(shown, face["label"], token.size_pt) * 25.4 / 72
        if x < margin or x + advance > width - margin + .01 or advance > maximum + .01:
            raise ValueError(f'“{text}” needs {advance:.1f} mm; this central column has {maximum:.1f} mm. Edit the copy or layout.')
        with TTFont(face["path"]) as font:
            cmap = font.getBestCmap()
            if any(ord(c) not in cmap for c in shown if not c.isspace() and c != "℮"):
                raise ValueError(f'The selected {role} font cannot draw every character in “{text}”.')
        if baseline - token.size_pt * 25.4 / 72 < margin or baseline + 1.2 > height - margin:
            raise ValueError("Required text crosses the proposed safe area.")
        node = TextRun(name=copy_id or role, text=text, x=x + advance if role == "arabic" else x,
                       y=baseline, font=token.font_role, size_pt=token.size_pt, color=ink,
                       align="right" if role == "arabic" else "left", rtl=role == "arabic")
        (front if surface == "body.front" else back).append(node)
        layout.append(dict(copy_id=copy_id, surface_id=surface, text=text, x_mm=x, baseline_mm=baseline,
                           width_mm=advance, font=face["postscript"], size_pt=token.size_pt))

    def wrapped(text, role, baseline, max_lines, *, surface="body.front", copy_id):
        from apps.ire.estimated_sign import width as sign_width
        token, face = tokens[role], fonts[role]
        lines = []
        for paragraph in text.split("\n"):
            current = ""
            for word in paragraph.split(" "):
                trial = current + " " + word if current else word
                if current and sign_width(trial, face["label"], token.size_pt) * 25.4 / 72 > 21:
                    lines.append(current); current = word
                else:
                    current = trial
            lines.append(current)
        if len(lines) > max_lines:
            raise ValueError(f'“{text}” needs more than {max_lines} lines. The copy is kept; revise its layout.')
        for index, text_line in enumerate(lines):
            line(text_line, role, baseline + index * (8.2 if role == "name" else 3.5),
                 surface=surface, copy_id=copy_id)

    wrapped(spec.required_copy.name, "name", 15.0, 2, copy_id="name")
    line(spec.required_copy.descriptor, "body", 27.5, copy_id="descriptor")
    line(spec.required_copy.arabic, "arabic", 31.8, copy_id="arabic")
    line(spec.required_copy.benefit, "body", 20.0, surface="body.back", copy_id="benefit")
    wrapped(spec.required_copy.care, "body", 26.0, 3, surface="body.back", copy_id="care")
    wrapped(spec.required_copy.volume, "body", 49.0, 2, surface="body.back", copy_id="volume")
    logo_hash = next(pin.sha256 for pin in spec.assets if pin.role == "approved_logo")
    logo = AssetRef(name="Approved BBROSE vector mark", asset_id="brand-mark:" + logo_hash,
                   x=7.0, y=3.0, w=18.0, h=18.0 * .208591, recolor=ink)
    a = spec.illustration
    # Entire original bitmap is embedded. Its upper part is deliberately covered
    # by the opaque quiet field, not erased or regenerated. The crop is declared.
    visible = [dict(op="M", x=0, y=a.visible_from_y_mm), dict(op="L", x=width, y=a.visible_from_y_mm),
               dict(op="L", x=width, y=height), dict(op="L", x=0, y=height), dict(op="Z")]
    background = lambda: Rect(name="Proposed opaque ivory ink field", x=0, y=0, w=width, h=height,
                               fill=SolidFill(color=Color.from_hex(spec.palette.dominant)))
    root = Group(name="BODY FRONT", role="artwork", children=[background(),
        Group(name="Original raster — declared lower crop", role="decoration", children=[
            Image(name="Solar gesture", src=str(paths[a.asset_id]), x=a.x_mm, y=a.y_mm,
                  w=a.width_mm, h=a.height_mm, clip=visible)]),
        Group(name="LOGO", role="logo", children=[logo]),
        Group(name="LIVE TYPE", role="typography", children=front)])
    inside = Group(name="BODY BACK", role="artwork", children=[background(),
        Group(name="LOGO", role="logo", children=[logo.model_copy(deep=True)]),
        Group(name="LIVE TYPE", role="typography", children=back),
        Rect(name="Amber rule", x=5.5, y=13, w=21, h=.25, fill=SolidFill(color=Color.from_hex(spec.palette.accent)))])
    document = Document(page_w=width, page_h=height, title="Sun Repair — proposed front and back masters",
                        metadata={"typography_surface": "apps/ire/compose_hybrid_bottle.py::compose",
                                  "layers/1.0": True, "logical_text/1.0": True, "surface_names": ["BODY FRONT", "BODY BACK"],
                                  "design_spec_hash": digest(spec.model_dump()), "design_revision": spec.revision,
                                  "materials": {"body": "clear_glass", "closure": "chrome_spray"},
                                  "production_ready": False}, root=root, inside=inside)
    return document, dict(effective_ppi=ppi, live_copy=spec.required_copy.model_dump(), text_runs=layout,
                          copy_surfaces=spec.copy_surfaces,
                          illustration_crop={"visible_y_mm": [a.visible_from_y_mm, height], "original_pixels_retained": True},
                          fonts={k: {f: v[f] for f in ("postscript", "sha256", "record")} for k, v in fonts.items()})


def svg(document, spec, *, back=False):
    """Portable SVG of the SAME graph: embedded assets/fonts, logical live type."""
    paths, _ = resolve_assets(spec)
    fonts = resolve_fonts(spec.type_tokens)
    ns = "http://www.w3.org/2000/svg"
    ET.register_namespace("", ns)
    def el(tag, attrs=None):
        return ET.Element("{" + ns + "}" + tag, {k: str(v) for k, v in (attrs or {}).items()})
    root = el("svg", {"width": f"{document.page_w}mm", "height": f"{document.page_h}mm",
                      "viewBox": f"0 0 {document.page_w} {document.page_h}"})
    ET.SubElement(root, "{" + ns + "}metadata").text = "DesignSpec " + document.metadata["design_spec_hash"]
    defs = ET.SubElement(root, "{" + ns + "}defs")
    style = ET.SubElement(root, "{" + ns + "}style")
    style.text = "\n".join("@font-face{font-family:'%s';src:url(data:font/ttf;base64,%s) format('truetype');}" %
                           (role, base64.b64encode(open(row["path"], "rb").read()).decode()) for role, row in fonts.items())
    roles = {t.font_role: t.role for t in spec.type_tokens}
    def hex_color(color):
        return "#" + "".join(f"{round(v * 255):02X}" for v in (color.r, color.g, color.b))
    def draw(node):
        if node.type == "group":
            group = el("g", {"data-name": node.name})
            for child in node.children:
                group.append(draw(child))
            return group
        if node.type == "rect":
            return el("rect", dict(x=node.x, y=node.y, width=node.w, height=node.h, fill=hex_color(node.fill.color)))
        if node.type == "image":
            attrs = {"x": node.x, "y": node.y, "width": node.w, "height": node.h,
                     "href": "data:image/png;base64," + base64.b64encode(paths[spec.illustration.asset_id].read_bytes()).decode()}
            if node.clip:
                clip = el("clipPath", {"id": "illustration-crop", "clipPathUnits": "userSpaceOnUse"})
                commands = " ".join(segment.op + (f" {segment.x} {segment.y}" if segment.op in ("M", "L") else "")
                                    for segment in node.clip)
                clip.append(el("path", {"d": commands}))
                defs.append(clip)
                attrs["clip-path"] = "url(#illustration-crop)"
            return el("image", attrs)
        if node.type == "asset_ref":
            logo = copy.deepcopy(ET.parse(paths["bbrose-approved-logo"]).getroot())
            logo.attrib.update(x=str(node.x), y=str(node.y), width=str(node.w), height=str(node.h))
            for part in logo.iter():
                if part.tag.endswith("path"):
                    part.set("fill", hex_color(node.recolor))
            return logo
        if node.type == "text":
            attrs = {"x": node.x, "y": node.y, "font-family": roles[node.font],
                               "font-size": node.size_pt * 25.4 / 72, "fill": hex_color(node.color),
                               "direction": "rtl" if node.rtl else "ltr", "text-anchor": "start",
                               "unicode-bidi": "plaintext", "xml:space": "preserve",
                               "font-kerning": "none", "font-variant-ligatures": "none"}
            if "℮" in node.text:
                from apps.ire.estimated_sign import pieces
                group = el("g", {"aria-label": node.text})
                for piece in pieces(node.text, node.x, node.y, node.size_pt, fonts[roles[node.font]]["label"]):
                    if piece[0] == "text":
                        child = el("text", dict(attrs, x=piece[2])); child.text = piece[1]
                    else:
                        commands = " ".join(op[0] + " ".join(f"{v:.8f}" for v in op[1:]) for op in piece[1])
                        child = el("path", {"d": commands, "fill": hex_color(node.color), "data-symbol": "℮"})
                    group.append(child)
                return group
            text = el("text", attrs)
            text.text = node.text
            return text
        raise ValueError(f"Unsupported SVG node {node.type}; no element may be silently omitted.")
    root.append(draw(document.inside if back else document.root))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
