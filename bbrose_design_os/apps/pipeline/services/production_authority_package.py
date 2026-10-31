"""Deterministic renderer for the production-authority preflight package.

The six JSON records under ``docs/production_authority/`` are the source of
truth. The three PDFs and the PNG board are *derived* from them here, so a
record can never quietly drift from the documents the owner actually reads —
edit the record, re-run :func:`render_package`, and the paper follows.

This module renders. It does not decide: it never sets a gate, never marks a
check passed, and never sends anything. Illustrator verification in particular
cannot be satisfied from here, and the renderer has no code path that would
write a pass into it.
"""
import json
import os

from django.conf import settings

DOCS = os.path.join(settings.BASE_DIR, "docs")
PA = os.path.join(DOCS, "production_authority")
VQ2 = os.path.join(DOCS, "visual_quality", "vq2")
VQ3 = os.path.join(DOCS, "visual_quality", "vq3")

BG = (250, 249, 248)
INK = (43, 43, 49)
PAGE_W, PAGE_H = 1500, 792
THUMB_W, THUMB_H, THUMB_Y = 168, 400, 340

RECORDS = {
    "preflight": "production_authority_preflight.json",
    "checklist": "illustrator_execution_verification_checklist.json",
    "template": "illustrator_execution_verification_result_template.json",
    "spec": "supplier_evidence_request_specification.json",
    "drafts": "production_supplier_request_drafts.json",
    "gates": "production_authority_gate.json",
    "receipts": "illustrator_execution_verification_receipts.json",
    "dispatch": "supplier_evidence_request_dispatch.json",
    # the clean-up, 2026-10-04 (his S2 answer): these two moved to docs/archive/supplier/
    "manifest": "../archive/supplier/supplier_dispatch_manifest.json",
    "sent_validation": "../archive/supplier/supplier_sent_evidence_validation.json",
    "outreach_deferral": "supplier_outreach_deferral.json",
}

# the records the preflight also holds under these keys; each is re-embedded
# from its file when the file exists, so the preflight is derived and never
# hand-edited
EMBEDDED = (
    ("supplier_dispatch", "dispatch"),
    ("supplier_manifest", "manifest"),
    ("supplier_sent_validation", "sent_validation"),
    ("supplier_outreach_deferral", "outreach_deferral"),
)


def load(name):
    with open(os.path.join(PA, RECORDS[name]), encoding="utf-8") as fh:
        return json.load(fh)


def save(name, data):
    path = os.path.join(PA, RECORDS[name])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
    return path


def _font(size, bold=False):
    from PIL import ImageFont
    names = (("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc") if bold else
             ("/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/Helvetica.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    for path in names:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _blob(obj):
    """A JSON body as the PDFs render it — one token per line, no wrapping."""
    return json.dumps(obj, indent=1, ensure_ascii=False).splitlines()


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------

def _wrap(c, text, font, size, avail, indent=""):
    """Greedy word wrap against the real glyph widths, so a long note or a
    long JSON string value cannot run off the right edge of the page."""
    if c.stringWidth(text, font, size) <= avail:
        return [text]
    out, line = [], ""
    for word in text.split(" "):
        probe = f"{line} {word}" if line else word
        if line and c.stringWidth(probe, font, size) > avail:
            out.append(line)
            line = indent + word
        else:
            line = probe
    if line:
        out.append(line)
    return out


def _pdf(path, title, sections):
    """Render ``sections`` — (heading, [subtitle lines], [body lines]) — to PDF.

    Pagination is by line budget rather than by section so a long record spills
    onto the next page instead of being truncated.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    width, height = A4
    margin, lead = 42, 12.4
    c = canvas.Canvas(path, pagesize=A4)
    y = height - margin

    def newpage():
        nonlocal y
        c.showPage()
        y = height - margin

    def line(text, font="Helvetica", size=8.6, gap=lead):
        """Draw one logical line, wrapping to the page rather than running off
        it. Continuations keep the original indent so JSON stays readable."""
        nonlocal y
        avail = width - 2 * margin
        indent = " " * (len(text) - len(text.lstrip(" ")))
        for chunk in _wrap(c, text, font, size, avail, indent):
            if y < margin + gap:
                newpage()
            c.setFont(font, size)
            c.drawString(margin, y, chunk)
            y -= gap

    c.setFont("Helvetica-Bold", 15)
    for part in title.split("\n"):
        if y < margin + 20:
            newpage()
        c.drawString(margin, y, part)
        y -= 19
    y -= 6

    for heading, subs, body in sections:
        if y < margin + 60:
            newpage()
        y -= 4
        line(heading, "Helvetica-Bold", 10.6, lead + 3)
        for s in subs:
            line(s, "Helvetica-Oblique", 8.6)
        for b in body:
            line(b)
        y -= 5

    c.save()
    return os.path.getsize(path)


def _receipt_subs(rec):
    """What has actually arrived for Gate A, stated before the requirements —
    a re-upload of the accepted source must never read as progress."""
    if not rec:
        return []
    subs = []
    for r in rec["receipts"]:
        subs.append(
            f'Receipt {r["n"]} ({r["received_at"]}): '
            f'{", ".join(r["codes"])} — {r["gate_a_effect"]}.')
        subs.append(r["finding"])
    outstanding = [a["filename"] for a in rec["awaiting"] if not a["received"]]
    if outstanding:
        subs.append("Still required: " + ", ".join(outstanding) +
                    " — saved and reopened in Illustrator, not overwriting the "
                    "accepted source.")
    subs.append(rec["eps_text_note"])
    return subs


# §BH46(e): each hand-kept production blocker code — the history it is — is
# paired with the gate whose cause the preflight reads from the gate record.
BLOCKER_GATE = {
    "PRODUCTION_GEOMETRY": "B_supplier_geometry",
    "PRODUCTION_FLAT_ARTWORK": "C_flat_artwork",
    "PRODUCTION_COLOR_SEPARATION": "D_colour_separation",
    "PRODUCTION_MATERIAL_SPECIFICATION": "E_material_specification",
}


def preflight_sections(pre, spec, drafts, gates, receipts=None):
    blocked = [g for g in BLOCKER_GATE.values()
               if gates["gates"][g]["state"] != "PASSED"]
    iev = pre["illustrator_verification"]
    sup = [f'{s["supplier"]} — {s.get("subject", "")}'
           for s in drafts["suppliers"]]
    return [
        ("What this is",
         ["PRODUCTION AUTHORITY PREFLIGHT STARTED — all five gates BLOCKED. "
          "Two owner actions required; nothing was sent and nothing changed.",
          "Not a design stage. It defines what production authority requires "
          "and prepares the requests; it grants nothing."], []),
        ("1. Closed workstreams", [], _blob(pre["closed_workstreams"])),
        ("2. Frozen accepted identities", [], _blob(pre["frozen"])),
        ("3. Illustrator verification requirements",
         [f'{iev["state"]} — cannot be performed here',
          iev["cannot_be_performed_here"]] + _receipt_subs(receipts),
         _blob({"checks": [c["check"] for c in iev["checks"]],
                "actions": [a["action"] for a in iev["actions"]]})),
        ("4. Bottle evidence requirements", [], _blob(spec["container_evidence"])),
        ("5. Closure evidence requirements", [], _blob(spec["closure_evidence"])),
        ("6. Compatibility requirements", [],
         _blob(spec["compatibility_evidence"])),
        ("7. Material evidence requirements", [], _blob(spec["material_evidence"])),
        ("8. Print evidence requirements",
         [spec["projected_to_wrap_conversion"]], _blob(spec["print_evidence"])),
        ("9. Supplier request drafts",
         [f'{drafts["status"]} — {len(drafts["suppliers"])} drafts, '
          f'{drafts["send_count"]} sent'
          + (f'; SUPERSEDED-BY {pre["supplier_dispatch"]["superseded_by"]} '
             '— the system never contacts suppliers; the drafts are history'
             if "supplier_dispatch" in pre
             and "superseded_by" in pre["supplier_dispatch"] else ''),
          "Full send-ready subject and body prose for every draft is in "
          "production_supplier_request_drafts.json."],
         _blob({"suppliers": sup,
                "required_asks": drafts["required_asks"],
                "attachments": drafts["attachments"],
                "no_response_is_not_evidence":
                    drafts["no_response_is_not_evidence"]})),
        ("10. Production authority gates", [],
         _blob({k: v for k, v in gates.items()
                if k not in ("record_type", "created_at")})),
        ("11. Current blockers",
         [f"{len(blocked)} OF {len(BLOCKER_GATE)} PRODUCTION GATES BLOCKED"
          if blocked else "NO PRODUCTION GATE BLOCKED"] +
         ([pre["blockers_note"]] if pre.get("blockers_note") else []) +
         [pre["blockers_cause_note"]],
         _blob({"blockers": pre["blockers"],
                "blockers_cause": pre["blockers_cause"]})),
        ("12. Exact owner actions required", [],
         _blob(pre["owner_actions_required"])),
    ]


def checklist_sections(iev, tpl, receipts=None):
    received = [] if not receipts else [
        ("0. What has arrived so far", _receipt_subs(receipts),
         _blob({"verification_copy_received":
                receipts["verification_copy_received"],
                "awaiting": [a["filename"] for a in receipts["awaiting"]
                             if not a["received"]],
                "acceptance_rules": receipts["acceptance_rules"]}))]
    # The previous attempt failed on colour, and colour was in none of the
    # structural checks. Both go in the document the owner actually opens.
    prev = iev.get("previous_subject")
    failed = [] if not prev else [
        ("0b. The previous attempt FAILED — do not use that file",
         ["Opening it in Illustrator produced one solid black silhouette. "
          "Every visible object had been written as 0.0000 0.0000 0.0000 Xa "
          "and the document declared Black only, so the source never carried "
          "the approved colours. It is preserved unchanged for audit and is "
          "NOT production authority. Use the corrected source named below.",
          *prev["codes"]],
         _blob({"failed_file": prev["file"],
                "failed_sha256_16": prev["sha256_16"],
                "preserved": prev["preserved"],
                "overwritten": prev["overwritten"]}))]
    colors = [] if not iev.get("expected_colors") else [
        ("2b. Colours — every object must show one of these, none may be black",
         ["Confirm this visually in Illustrator. The corrected source carrying "
          "the right numbers is NOT evidence that Illustrator honoured them.",
          "sRGB concept artwork only — not CMYK, not Pantone, not spot, no "
          "supplier ink authority."],
         _blob(iev["expected_colors"]))]
    return received + failed + [
        ("1. Subject",
         [f'{iev["state"]} — {iev["must_be_performed_in"]}',
          iev["cannot_be_performed_here"]],
         _blob({k: v for k, v in (
             ("subject_file", iev["subject_file"]),
             ("subject_sha256_16", iev["subject_sha256_16"]),
             ("subject_format", iev["subject_format"]),
             ("verification_state", iev.get("verification_state")),
             ("do_not_overwrite_accepted_source",
              iev["do_not_overwrite_accepted_source"])) if v is not None})),
        ("2. Expected structure", [],
         _blob({"expected_layers": iev["expected_layers"],
                "expected_objects": iev["expected_objects"],
                "expected_logo_components": iev["expected_logo_components"],
                "expected_rose_glyphs": iev["expected_rose_glyphs"],
                "expected_damascena_glyphs": iev["expected_damascena_glyphs"],
                "expected_supporting_glyphs":
                    iev["expected_supporting_glyphs"]})),
        *colors,
        ("3. Checks — record PASS/FAIL against every line",
         [], [f'{c["n"]:>3}. [ ] {c["check"]}' for c in iev["checks"]]),
        ("4. Actions — perform in order",
         [], [f'{a["n"]:>3}. [ ] {a["action"]}' for a in iev["actions"]]),
        ("5. Recording the result",
         [tpl["instructions"]],
         _blob({"template":
                "illustrator_execution_verification_result_template.json",
                "gate": iev["gate"], "gate_state": iev["gate_state"]})),
    ]


def spec_sections(spec):
    return [
        ("1. Container evidence", [], _blob(spec["container_evidence"])),
        ("2. Closure evidence", [], _blob(spec["closure_evidence"])),
        ("3. Compatibility evidence", [], _blob(spec["compatibility_evidence"])),
        ("4. Material evidence", [], _blob(spec["material_evidence"])),
        ("5. Print evidence", [], _blob(spec["print_evidence"])),
        ("6. Authority limits",
         [spec["concept_authority_note"],
          spec["projected_to_wrap_conversion"]],
         _blob({"material_spec_inferred_from_vq3_visuals":
                spec["material_spec_inferred_from_vq3_visuals"],
                "vq3_is_visualization_only": spec["vq3_is_visualization_only"]})),
    ]


# --------------------------------------------------------------------------
# PNG board
# --------------------------------------------------------------------------

def board_lines(pre, drafts, gates, receipts=None):
    g = gates["gates"]
    gate_a = (f'Gate A Illustrator execution — '
              f'{g["A_illustrator_execution"]["state"]}, pending human '
              "execution")
    if receipts and not receipts["verification_copy_received"]:
        gate_a += (f' · {len(receipts["receipts"])} receipt(s), original '
                   "source re-uploaded, verification copy NOT received")
    passed = sum(1 for k in g if g[k]["state"] == "PASSED")

    def cause(key):
        # §BH46(e): the cause is read from the gate record, not remembered here
        return g[key]["cause"] if "cause" in g[key] else g[key]["blocked_by"]

    return [
        f"PRODUCTION AUTHORITY PREFLIGHT — {passed} of 5 gates passed; gates B to "
        "E wait on the owner-supplied spec pack, intaken item by item. Nothing "
        "was sent.",
        "VQ-1, VQ-2, Complete Product and VQ-3 all closed and untouched",
        f'{len(pre["frozen"])} frozen identities re-verified, '
        f'{len(pre["frozen_drift"])} drift',
        gate_a,
        f'Gate B supplier geometry — {g["B_supplier_geometry"]["state"]}, '
        f'{cause("B_supplier_geometry")}',
        f'Gate C flat artwork — {g["C_flat_artwork"]["state"]}, '
        f'{cause("C_flat_artwork")}',
        f'Gate D colour separation — {g["D_colour_separation"]["state"]}, '
        f'{cause("D_colour_separation")}',
        f'Gate E material specification — '
        f'{g["E_material_specification"]["state"]}, '
        f'{cause("E_material_specification")}',
        f'{len(drafts["suppliers"])} supplier drafts {drafts["status"]}, '
        f'{drafts["send_count"]} sent, '
        f'{len(drafts["attachments"]["currently_attached"])} attachments',
        "projected front-view widths must NOT be converted to wrap dimensions",
        "evidence authority: supplier drawing > written confirmation > sample "
        "> material spec > print zone > concept",
        "concept never overrides qualified production evidence",
        "packaging NOT started · no provider call · no image generation",
        f'OWNER ACTION: {gates["next_required_owner_action"][:96]}',
    ]


def render_board(path, lines):
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (PAGE_W, PAGE_H), BG)
    d = ImageDraw.Draw(im)
    d.text((22, 20), "PRODUCTION AUTHORITY PREFLIGHT", font=_font(26), fill=INK)
    y = 62
    for text in lines:
        d.text((22, y), text, font=_font(13), fill=INK)
        y += 18.8

    for x, src in ((22, os.path.join(VQ2, "vq2_a2_r2_final_clean.png")),
                   (502, os.path.join(VQ3, "vq3_m3_warm_rose_gold.png"))):
        if not os.path.exists(src):
            continue
        thumb = Image.open(src).convert("RGB")
        thumb.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
        im.paste(thumb, (x, THUMB_Y))

    im.save(path)
    return im.size


# --------------------------------------------------------------------------

def render_package():
    """Rebuild every derived document from the records. Returns a manifest."""
    pre, iev = load("preflight"), load("checklist")
    tpl, spec = load("template"), load("spec")
    drafts, gates = load("drafts"), load("gates")
    receipts = load("receipts")

    # the preflight record embeds the others — re-embed so they cannot diverge
    pre["illustrator_verification"] = iev
    pre["supplier_evidence_specification"] = spec
    pre["supplier_drafts"] = drafts
    pre["gates"] = gates
    pre["illustrator_receipts"] = receipts
    for key, name in EMBEDDED:
        if os.path.exists(os.path.join(PA, RECORDS[name])):
            pre[key] = load(name)
    # §BH46(e): the cause of every production block is read from the gate
    # record beside the hand-kept code, never typed beside it
    pre["blockers_cause"] = {k: gates["gates"][g]["cause"]
                             for k, g in BLOCKER_GATE.items()}
    pre["blockers_cause_note"] = ("the codes are kept as the history they are; "
                                  "the cause of each production block is read "
                                  "from the gate record (§BH46)")

    sections = preflight_sections(pre, spec, drafts, gates, receipts)
    pre_pdf = os.path.join(PA, "production_authority_preflight.pdf")
    size = _pdf(pre_pdf, "PRODUCTION AUTHORITY PREFLIGHT 1 — VERIFICATION,\n"
                         "EVIDENCE AND GATES", sections)

    chk_pdf = os.path.join(PA, "illustrator_execution_verification_checklist.pdf")
    chk_size = _pdf(chk_pdf, "ILLUSTRATOR EXECUTION VERIFICATION CHECKLIST",
                    checklist_sections(iev, tpl, receipts))

    spec_pdf = os.path.join(PA, "supplier_evidence_request_specification.pdf")
    spec_size = _pdf(spec_pdf, "SUPPLIER EVIDENCE REQUEST SPECIFICATION",
                     spec_sections(spec))

    png = os.path.join(PA, "production_authority_preflight.png")
    png_size = render_board(png, board_lines(pre, drafts, gates, receipts))

    pre["section_titles"] = [s[0] for s in sections]
    pre["sections"] = len(sections)
    pre["pdf"] = {"path": "docs/production_authority/"
                          "production_authority_preflight.pdf",
                  "sections": len(sections), "size_bytes": size}
    pre["png"] = {"path": "docs/production_authority/"
                          "production_authority_preflight.png",
                  "size": list(png_size)}
    iev["pdf"] = {"path": "docs/production_authority/"
                          "illustrator_execution_verification_checklist.pdf",
                  "sections": 5, "size_bytes": chk_size}
    pre["illustrator_verification"] = iev

    save("checklist", iev)
    save("preflight", pre)
    return {"preflight_pdf": size, "checklist_pdf": chk_size,
            "spec_pdf": spec_size, "png": png_size,
            "sections": len(sections)}
