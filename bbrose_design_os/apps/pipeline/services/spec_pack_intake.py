"""Owner-supplied spec pack intake — §BH46.

The system never contacts suppliers. The owners of the companies deal with their
suppliers directly and hand the product information — drawings, print zones,
decoration process, material specification — to the designer, which is this
system. Everything it needs is GIVEN to it; it acquires nothing. This module is
the intake: it READS a document the owner placed, VALIDATES it against the item
it is said to satisfy, records PROVENANCE (who handed it over, when, the sha256
measured here) and flips the ITEM — never the gate — to SATISFIED. It may
REFUSE a document, by name. It has no fetcher and no transport.

THE RULED LOCATION, beside production_authority/:

  docs/production_authority_intake/
    spec_pack/                the documents the owner places
    spec_pack_manifest.json   the owner's mapping: which document satisfies
                              which item, who handed it over, when, and the
                              sha256 as handed over (optional; measured here)
    intake_state.json         derived on every run: one entry per item
    intake_provenance.json    derived on every run: one entry per accepted
                              document, with the sha256 measured at intake
    dry_run.json, dry_run.md  derived: what the pack as it stands would
                              satisfy and would be refused, item by item,
                              with the reason, and what each missing item
                              needs — in the owner's words

The nineteen items are the `requires` lists of gates B to E, unchanged. What
"satisfies" each one means is written below in words an owner can act on, and
is what the checks measure.
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone

from django.conf import settings

DOCS_REL = "docs/production_authority_intake"
INTAKE = os.path.join(settings.BASE_DIR, "docs", "production_authority_intake")
SPEC_PACK = os.path.join(INTAKE, "spec_pack")
MANIFEST = os.path.join(INTAKE, "spec_pack_manifest.json")
OUT_STATE = os.path.join(INTAKE, "intake_state.json")
OUT_PROVENANCE = os.path.join(INTAKE, "intake_provenance.json")

MISSING = "MISSING"
REFUSED = "REFUSED"
SATISFIED = "SATISFIED"

# Refusals, by name. Every one carries a sentence for the owner.
WRONG_PRODUCT = "WRONG_PRODUCT"
NO_DIMENSIONS = "NO_DIMENSIONS"
NO_CERTIFICATE = "NO_CERTIFICATE"
NO_PROVENANCE = "NO_PROVENANCE"
SHA_MISMATCH = "SHA_MISMATCH"
FILE_MISSING = "FILE_MISSING"
WRONG_KIND = "WRONG_KIND"
UNREADABLE_KIND = "UNREADABLE_KIND"
NOT_INSPECTABLE = "NOT_INSPECTABLE"
CONTENT_ABSENT = "CONTENT_ABSENT"
UNKNOWN_ITEM = "UNKNOWN_ITEM"

# The product every document must name: the 30 ml cylindrical frosted-glass
# cosmetic serum bottle with its dropper closure.
PRODUCT_CAPACITY = re.compile(r"\b30\s?(?:ml|millilit)", re.I)
ANY_CAPACITY = re.compile(r"\b(\d{1,4})\s?(?:ml|millilit)", re.I)
PRODUCT_WORDS = re.compile(r"serum|dropper|frosted|pipette", re.I)

DIMENSION = re.compile(
    r"\b\d+(?:[.,]\d+)?\s?(?:mm|millimet\w*|cm|centimet\w*|µm|um|in\b|inch\w*)\b",
    re.I)
MIN_DIMENSIONS_ON_A_DRAWING = 2
TOLERANCE = re.compile(r"±|\+/-|\+-|\btolerance", re.I)
CERTIFICATE = re.compile(
    r"certificate|datasheet|data sheet|specification sheet|spec sheet|"
    r"\bTDS\b|\bSDS\b|\bMSDS\b|\bCOA\b|\bCoC\b|conformity|compliance|"
    r"technical data", re.I)
PRODUCT_CODE = re.compile(
    r"(?:product|item|part|article|catalog(?:ue)?|sku)\s?(?:code|no\.?|number|#|ref)"
    r"|\bSKU\b|\bP/N\b", re.I)
COMPATIBILITY = re.compile(r"compatib|fits?\b|assembl|leak|torque|mate\b", re.I)
PRINT_ZONE = re.compile(r"print[- ]?zone|printable area|print(?:ing)? area|decoration area", re.I)
WRAP = re.compile(r"\bwrap|circumference|unwrap|flat artwork|develop(?:ed|ment)", re.I)
SAFE_ZONE = re.compile(r"safe[- ]?zone|safe margin|bleed|no[- ]print|keep[- ]out|clearance", re.I)
PROCESS = re.compile(
    r"screen[- ]?print|silk[- ]?screen|pad[- ]?print|hot[- ]?stamp|foil|decal|"
    r"uv[- ]?print|digital print|label", re.I)
LIMITS = re.compile(
    r"limit|maximum|minimum|max\.?\b|min\.?\b|cannot|not possible|registration|"
    r"line width|opacity|coverage", re.I)
COLOUR_SYSTEM = re.compile(r"pantone|\bpms\b|cmyk|spot colou?r", re.I)
INK_FOIL = re.compile(r"\bink|\bfoil", re.I)
GLASS = re.compile(r"glass|soda[- ]lime|borosilicate|flint|type\s?(?:i|ii|iii)\b", re.I)
COLLAR = re.compile(r"collar|alumini?um|anodi[sz]|shell|ferrule", re.I)
CLOSURE = re.compile(
    r"closure|dropper|pipette|bulb|elastomer|rubber|silicone|nitrile|"
    r"\bcap\b|teat", re.I)
FROSTING = re.compile(r"frost|etch|acid|sandblast|satin|matte?\b", re.I)
COATING = re.compile(r"coat|spray|lacquer|paint|varnish", re.I)
FINISH_OPTIONS = re.compile(r"colou?r|finish|option|gloss|matte?\b|metallic", re.I)

DRAWING_KINDS = (".pdf", ".dxf", ".svg", ".ai", ".txt", ".md")
DOCUMENT_KINDS = (".pdf", ".txt", ".md", ".json", ".csv", ".html", ".htm")
IMAGE_KINDS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".gif")
BINARY_CAD_KINDS = (".dwg", ".step", ".stp", ".iges", ".igs", ".x_t", ".sldprt")


def _item(gate, name, kind, satisfies_when, checks):
    return {"gate": gate, "item": name, "kind": kind,
            "satisfies_when": satisfies_when, "checks": tuple(checks)}


#: The nineteen. `item` is the gate's `requires` text, verbatim; `kind` names
#: the document that can satisfy it; `satisfies_when` is for the owner;
#: `checks` are what this module measures, in the order it reports them.
ITEMS = (
    _item("B_supplier_geometry", "qualified bottle drawing", "drawing",
          "a supplier's technical drawing of THIS 30 ml frosted-glass serum bottle "
          "(PDF, DXF or a dimensioned text table) that carries the body diameter, "
          "the overall height, the shoulder height and the neck finish as numbers "
          "with units",
          ("product", "dimensions")),
    _item("B_supplier_geometry", "qualified closure drawing", "drawing",
          "a supplier's technical drawing of the dropper closure — collar, bulb, "
          "pipette, dip tube — with its dimensions as numbers with units, naming "
          "the bottle it fits",
          ("product", "dimensions", "closure")),
    _item("B_supplier_geometry", "product codes", "statement",
          "the supplier's own product code for the bottle and for the closure, "
          "in a document that names this product",
          ("product", "product_code")),
    _item("B_supplier_geometry", "tolerances", "statement",
          "the dimensional tolerances the supplier holds for this bottle and "
          "closure, as ± values or a tolerance table with units",
          ("product", "tolerance", "dimensions")),
    _item("B_supplier_geometry", "compatibility evidence", "statement",
          "the supplier's written confirmation that the quoted bottle and "
          "closure are a compatible pair — a fit, assembly or leak statement — "
          "naming this product",
          ("product", "compatibility")),
    _item("C_flat_artwork", "supplier print-zone drawing", "drawing",
          "the supplier's print-zone drawing for this bottle: the printable "
          "area with its dimensions as numbers with units",
          ("product", "print_zone", "dimensions")),
    _item("C_flat_artwork", "wrap dimensions", "statement",
          "the flat artwork or wrap dimensions for this bottle — the developed "
          "width and height, or circumference and print height — as numbers "
          "with units",
          ("product", "wrap", "dimensions")),
    _item("C_flat_artwork", "safe zone", "statement",
          "the safe zone, safe margin or keep-out the supplier requires around "
          "the print area, as numbers with units",
          ("product", "safe_zone", "dimensions")),
    _item("C_flat_artwork", "decoration-process limitations", "statement",
          "what the supplier's decoration process on this item cannot do or "
          "limits — minimum line width, registration, coverage, maximum area",
          ("product", "process", "limits")),
    _item("D_colour_separation", "supplier decoration process", "statement",
          "which decoration process the supplier offers on this item, by name "
          "— screen printing, pad printing, hot stamping, foil, decal or UV "
          "printing",
          ("product", "process")),
    _item("D_colour_separation", "colour-system requirements", "statement",
          "which colour systems the supplier accepts artwork in for this item "
          "— Pantone, CMYK or spot colour — stated as a requirement",
          ("product", "colour_system")),
    _item("D_colour_separation", "Pantone/CMYK/spot guidance", "guidance",
          "the supplier's guidance on what it can hold to in each colour "
          "system it accepts — Pantone references, CMYK availability, the "
          "number of spot colours — and any tolerance it states",
          ("product", "colour_system", "limits")),
    _item("D_colour_separation", "ink or foil limitations", "statement",
          "which inks or foils are available for the process on this item and "
          "what they cannot reproduce — opacity, metallics, coverage",
          ("product", "ink_foil", "limits")),
    _item("E_material_specification", "supplier-confirmed glass", "certificate",
          "a certificate, datasheet or specification sheet for the glass of "
          "this bottle — type, composition, chemical resistance — from the "
          "supplier",
          ("product", "glass", "certificate")),
    _item("E_material_specification", "collar", "certificate",
          "a certificate, datasheet or specification sheet for the collar — "
          "aluminium grade, anodising or coating process, corrosion resistance",
          ("product", "collar", "certificate")),
    _item("E_material_specification", "closure", "certificate",
          "a certificate, datasheet or specification sheet for the closure's "
          "elastomer and pipette — compound, hardness, migration and "
          "chemical-resistance data",
          ("product", "closure", "certificate")),
    _item("E_material_specification", "frosting", "certificate",
          "a certificate, datasheet or specification sheet for the frosting "
          "method and its durability on this glass",
          ("product", "frosting", "certificate")),
    _item("E_material_specification", "coating", "certificate",
          "a certificate, datasheet or specification sheet for the coating or "
          "spraying system on this bottle — adhesion, durability, chemical "
          "resistance",
          ("product", "coating", "certificate")),
    _item("E_material_specification", "colour and finish options", "statement",
          "the colour and finish options the supplier offers on this bottle, "
          "collar and closure, with their tolerances where stated",
          ("product", "finish_options")),
)

ITEM_INDEX = {f"{i['gate']}/{i['item']}": i for i in ITEMS}

CHECK_SENTENCE = {
    "product": "names this product: 30 ml, and serum, dropper, frosted or pipette",
    "dimensions": f"carries at least {MIN_DIMENSIONS_ON_A_DRAWING} dimensions as "
                  "numbers with units (mm, cm, in)",
    "tolerance": "states a tolerance (±, +/- or the word)",
    "product_code": "states a product, item, part or catalogue code",
    "compatibility": "states fit, assembly, compatibility, torque or leak evidence",
    "print_zone": "names the print zone or printable area",
    "wrap": "names the wrap, circumference or flat/developed artwork",
    "safe_zone": "names the safe zone, safe margin, bleed or keep-out",
    "process": "names a decoration process (screen, pad, hot stamp, foil, decal, UV)",
    "limits": "states a limit — minimum, maximum, registration, coverage, cannot",
    "colour_system": "names a colour system — Pantone, PMS, CMYK or spot colour",
    "ink_foil": "names an ink or a foil",
    "glass": "names the glass type",
    "collar": "names the collar, its aluminium or its anodising",
    "closure": "names the closure — dropper, pipette, bulb, elastomer",
    "frosting": "names the frosting, etching or satin finish",
    "coating": "names the coating, spray, lacquer or paint",
    "finish_options": "names colour or finish options",
    "certificate": "is, or carries, a certificate, datasheet, specification "
                   "sheet or technical data (TDS, SDS, COA, CoC)",
}

CHECK_REFUSAL = {
    "product": WRONG_PRODUCT,
    "dimensions": NO_DIMENSIONS,
    "certificate": NO_CERTIFICATE,
}

CHECK_PATTERN = {
    "tolerance": TOLERANCE, "product_code": PRODUCT_CODE,
    "compatibility": COMPATIBILITY, "print_zone": PRINT_ZONE, "wrap": WRAP,
    "safe_zone": SAFE_ZONE, "process": PROCESS, "limits": LIMITS,
    "colour_system": COLOUR_SYSTEM, "ink_foil": INK_FOIL, "glass": GLASS,
    "collar": COLLAR, "closure": CLOSURE, "frosting": FROSTING,
    "coating": COATING, "finish_options": FINISH_OPTIONS,
    "certificate": CERTIFICATE,
}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def read_text(path):
    """The document's text, read from the placed file and nothing else.

    Returns (text, kind_refusal). A PDF (and an .ai, which is PDF-compatible)
    is read page by page; text kinds are read as UTF-8; an image carries no
    text this module can check; binary CAD is not inspectable here.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_KINDS:
        return "", UNREADABLE_KIND
    if ext in BINARY_CAD_KINDS:
        return "", NOT_INSPECTABLE
    if ext in (".pdf", ".ai"):
        try:
            import fitz
            doc = fitz.open(path)
            return "".join(page.get_text() for page in doc), None
        except Exception as exc:  # a file that is not a PDF underneath
            return "", f"{UNREADABLE_KIND}:{type(exc).__name__}"
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8", "replace"), None


def check_product(text):
    """The document names THIS product, or it is refused as WRONG_PRODUCT."""
    if PRODUCT_CAPACITY.search(text) and PRODUCT_WORDS.search(text):
        return True, "names the 30 ml serum/dropper product"
    other = sorted({m.group(1) for m in ANY_CAPACITY.finditer(text)})
    if other:
        return False, f"names another capacity ({', '.join(other)} ml) and not 30 ml"
    if PRODUCT_WORDS.search(text):
        return False, "names a serum/dropper product but not the 30 ml capacity"
    return False, "names no product"


def run_check(name, text):
    if name == "product":
        return check_product(text)
    if name == "dimensions":
        found = DIMENSION.findall(text)
        n = len(found)
        if n >= MIN_DIMENSIONS_ON_A_DRAWING:
            return True, f"{n} dimensions with units"
        return False, (f"{n} dimension(s) with units; a drawing needs at least "
                       f"{MIN_DIMENSIONS_ON_A_DRAWING}")
    pat = CHECK_PATTERN[name]
    m = pat.search(text)
    if m:
        return True, f"found '{m.group(0)}'"
    return False, "not found: " + CHECK_SENTENCE[name]


def _provenance_of(entry, manifest):
    """Who handed it over and when — from the entry, or the manifest's own
    top-level fields; both must be present, and the date must be a date."""
    who = entry["handed_over_by"] if "handed_over_by" in entry else (
        manifest["handed_over_by"] if "handed_over_by" in manifest else None)
    when = entry["handed_over_on"] if "handed_over_on" in entry else (
        manifest["handed_over_on"] if "handed_over_on" in manifest else None)
    problems = []
    if not who or not str(who).strip():
        problems.append("handed_over_by is missing")
    if not when or not re.fullmatch(r"20\d\d-\d\d-\d\d", str(when)):
        problems.append("handed_over_on is missing or is not a date (YYYY-MM-DD)")
    return who, when, problems


def inspect_document(entry, manifest, spec_pack=None):
    """One manifest entry: the file, its provenance, its text, and the verdict
    for every item it claims to satisfy. Nothing is fetched."""
    spec_pack = spec_pack if spec_pack is not None else SPEC_PACK
    rel = entry["file"] if "file" in entry else ""
    claims = list(entry["satisfies"]) if "satisfies" in entry else []
    path = os.path.join(spec_pack, rel)
    result = {"file": rel, "satisfies_claimed": claims, "exists": False,
              "sha256_measured": None, "sha256_declared": None,
              "handed_over_by": None, "handed_over_on": None,
              "refusals": [], "items": {}}
    who, when, problems = _provenance_of(entry, manifest)
    result["handed_over_by"], result["handed_over_on"] = who, when
    if problems:
        result["refusals"].append({"code": NO_PROVENANCE, "why": "; ".join(problems)})
    if not rel or not os.path.isfile(path):
        result["refusals"].append({"code": FILE_MISSING,
                                   "why": f"no file at spec_pack/{rel}"})
    else:
        result["exists"] = True
        with open(path, "rb") as fh:
            data = fh.read()
        result["sha256_measured"] = sha256_bytes(data)
        if "sha256" in entry and entry["sha256"]:
            result["sha256_declared"] = entry["sha256"]
            if entry["sha256"].lower() != result["sha256_measured"]:
                result["refusals"].append({
                    "code": SHA_MISMATCH,
                    "why": "the sha256 declared in the manifest is not the "
                           "sha256 of the file placed"})
    for key in claims:
        if key not in ITEM_INDEX:
            result["items"][key] = {"state": REFUSED, "refusals": [
                {"code": UNKNOWN_ITEM, "why": "not one of the nineteen items"}]}
            continue
        item = ITEM_INDEX[key]
        refusals = list(result["refusals"])
        checks = {}
        if result["exists"]:
            ext = os.path.splitext(rel)[1].lower()
            allowed = DRAWING_KINDS if item["kind"] == "drawing" else DOCUMENT_KINDS
            if ext in IMAGE_KINDS:
                refusals.append({"code": UNREADABLE_KIND,
                                 "why": "an image carries no text this module can "
                                        "check; place the drawing as a PDF, DXF or "
                                        "a text table with the dimensions"})
            elif ext in BINARY_CAD_KINDS:
                refusals.append({"code": NOT_INSPECTABLE,
                                 "why": "binary CAD is not inspected here; add a "
                                        "dimensioned PDF of the same drawing"})
            elif ext not in allowed:
                ext_label = ext if ext else "no extension"
                refusals.append({"code": WRONG_KIND,
                                 "why": f"{ext_label} is not a "
                                        f"{item['kind']} kind ({', '.join(allowed)})"})
            else:
                text, kind_refusal = read_text(path)
                if kind_refusal:
                    refusals.append({"code": kind_refusal.split(":")[0],
                                     "why": f"the file could not be read as text "
                                            f"({kind_refusal})"})
                elif not text.strip():
                    refusals.append({"code": CONTENT_ABSENT,
                                     "why": "the document has no readable text"})
                else:
                    for name in item["checks"]:
                        ok, why = run_check(name, text)
                        checks[name] = {"ok": ok, "why": why}
                        if not ok:
                            code = CHECK_REFUSAL[name] if name in CHECK_REFUSAL \
                                else CONTENT_ABSENT
                            refusals.append({"code": code,
                                             "why": f"{name}: {why}"})
        result["items"][key] = {
            "state": SATISFIED if not refusals else REFUSED,
            "checks": checks,
            "refusals": refusals,
        }
    return result


def load_manifest(path=None):
    path = path if path is not None else MANIFEST
    if not os.path.isfile(path):
        return {"record_type": "spec_pack_manifest/1.0", "documents": []}, None
    with open(path, "rb") as fh:
        data = fh.read()
    return json.loads(data.decode("utf-8")), sha256_bytes(data)


def validate(write=True, manifest_path=None, spec_pack=None,
             out_state=None, out_provenance=None):
    """Derive the intake state and the provenance record from the location as
    it stands on this run. An item is SATISFIED only by a placed document that
    passes every check for that item and carries provenance; the gate is not
    flipped here — it is computed from items by the gate record's generator."""
    manifest, manifest_sha = load_manifest(manifest_path)
    spec_pack = spec_pack if spec_pack is not None else SPEC_PACK
    documents = list(manifest["documents"]) if "documents" in manifest else []
    inspected = [inspect_document(d, manifest, spec_pack) for d in documents]
    generated_on = datetime.now(timezone.utc).date().isoformat()
    items = []
    for item in ITEMS:
        key = f"{item['gate']}/{item['item']}"
        satisfying = [r for r in inspected
                      if key in r["items"] and r["items"][key]["state"] == SATISFIED]
        refused = [r for r in inspected
                   if key in r["items"] and r["items"][key]["state"] == REFUSED]
        if satisfying:
            state = SATISFIED
        elif refused:
            state = REFUSED
        else:
            state = MISSING
        items.append({
            "gate": item["gate"], "item": item["item"], "kind": item["kind"],
            "state": state,
            "satisfies_when": item["satisfies_when"],
            "checks": [f"{c}: {CHECK_SENTENCE[c]}" for c in item["checks"]],
            "satisfied_by": [{"file": r["file"], "sha256": r["sha256_measured"],
                              "handed_over_by": r["handed_over_by"],
                              "handed_over_on": r["handed_over_on"]}
                             for r in satisfying],
            "refused": [{"file": r["file"],
                         "refusals": r["items"][key]["refusals"]}
                        for r in refused],
        })
    gates = {}
    for item in items:
        g = gates.setdefault(item["gate"], {"items_total": 0, "items_satisfied": 0,
                                            "items_refused": 0, "items_missing": 0})
        g["items_total"] += 1
        g[f"items_{item['state'].lower()}"] += 1
    for g in gates.values():
        g["all_items_satisfied"] = g["items_satisfied"] == g["items_total"]
    accepted = [r for r in inspected
                if any(v["state"] == SATISFIED for v in r["items"].values())]
    rec = {
        "record_type": "spec_pack_intake_state/1.0",
        "generated_on": generated_on,
        "location": DOCS_REL,
        "manifest": f"{DOCS_REL}/spec_pack_manifest.json",
        "manifest_sha256": manifest_sha,
        "documents_placed": len(documents),
        "documents_accepted": len(accepted),
        "documents_refused": len([r for r in inspected if r["items"] and not
                                  any(v["state"] == SATISFIED
                                      for v in r["items"].values())]),
        "items_total": len(items),
        "items_satisfied": sum(1 for i in items if i["state"] == SATISFIED),
        "items_refused": sum(1 for i in items if i["state"] == REFUSED),
        "items_missing": sum(1 for i in items if i["state"] == MISSING),
        "gates": gates,
        "items": items,
        "documents": inspected,
        "rule": "an item is SATISFIED only by a placed document that names this "
                "product, passes every check for that item and carries provenance "
                "(who handed it over, when, the sha256 measured here); the gate is "
                "computed from its items and is never flipped here",
        "this_module_fetches": False,
    }
    prov = {
        "record_type": "spec_pack_intake_provenance/1.0",
        "generated_on": generated_on,
        "documents": [{
            "file": r["file"], "sha256": r["sha256_measured"],
            "sha256_declared": r["sha256_declared"],
            "handed_over_by": r["handed_over_by"],
            "handed_over_on": r["handed_over_on"],
            "received_on": generated_on,
            "satisfies": [k for k, v in r["items"].items() if v["state"] == SATISFIED],
        } for r in accepted],
    }
    if write:
        for path, obj in ((out_state if out_state is not None else OUT_STATE, rec),
                          (out_provenance if out_provenance is not None
                           else OUT_PROVENANCE, prov)):
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, indent=1, ensure_ascii=False)
                fh.write("\n")
    return rec, prov


OUT_DRY_RUN_JSON = os.path.join(INTAKE, "dry_run.json")
OUT_DRY_RUN_MD = os.path.join(INTAKE, "dry_run.md")

GATE_TITLES = {
    "B_supplier_geometry": "Gate B — supplier geometry",
    "C_flat_artwork": "Gate C — flat artwork",
    "D_colour_separation": "Gate D — colour separation",
    "E_material_specification": "Gate E — material specification",
}


def dry_run(write=True, manifest_path=None, spec_pack=None,
            out_json=None, out_md=None):
    """What the spec pack as it stands would satisfy and would be refused, item
    by item, with the reason — and, for every item still missing, what a
    document must contain to satisfy it, in the owner's words. Reads the
    location and nothing else; flips nothing; writes only its two reports."""
    rec, _prov = validate(write=False, manifest_path=manifest_path,
                          spec_pack=spec_pack)
    rows = []
    for item in rec["items"]:
        row = {"gate": item["gate"], "item": item["item"], "kind": item["kind"],
               "would": item["state"], "needs": item["satisfies_when"],
               "checks": item["checks"], "because": []}
        if item["state"] == SATISFIED:
            row["because"] = [f"{d['file']} satisfies it (sha256 {d['sha256'][:16]}…, "
                              f"handed over by {d['handed_over_by']} on "
                              f"{d['handed_over_on']})" for d in item["satisfied_by"]]
        elif item["state"] == REFUSED:
            for d in item["refused"]:
                for r in d["refusals"]:
                    row["because"].append(f"{d['file']}: {r['code']} — {r['why']}")
        else:
            row["because"] = ["no document in the pack claims this item"]
        rows.append(row)
    out = {
        "record_type": "spec_pack_intake_dry_run/1.0",
        "generated_on": rec["generated_on"],
        "location": DOCS_REL,
        "documents_placed": rec["documents_placed"],
        "would_satisfy": rec["items_satisfied"],
        "would_refuse": rec["items_refused"],
        "missing": rec["items_missing"],
        "gates_that_would_pass": [g for g, v in rec["gates"].items()
                                  if v["all_items_satisfied"]],
        "items": rows,
        "this_run_flipped_nothing": True,
    }
    md = [
        "# Spec pack dry-run — what the pack as it stands would satisfy",
        "",
        f"Run on {out['generated_on']} over `{DOCS_REL}/spec_pack_manifest.json`: "
        f"{out['documents_placed']} document(s) placed. This run reads the location, "
        "flips nothing, and writes only this report.",
        "",
        f"**Would satisfy {out['would_satisfy']} of 19 · would refuse "
        f"{out['would_refuse']} · missing {out['missing']}.** Gates that would pass: "
        + (", ".join(out["gates_that_would_pass"]) if out["gates_that_would_pass"]
           else "none — a gate passes only when every one of its items is satisfied "
                "by intaken evidence."),
        "",
    ]
    for gate, title in GATE_TITLES.items():
        md += [f"## {title}", ""]
        for row in rows:
            if row["gate"] != gate:
                continue
            md += [f"### `{row['item']}` — **{row['would']}**", "",
                   f"**Needs:** {row['needs']}.", "",
                   "**Checked as:** " + "; ".join(row["checks"]) + ".", ""]
            for b in row["because"]:
                md.append(f"- {b}")
            md.append("")
    md += ["---", "",
           "Every document must carry provenance — who handed it over and when — or it "
           "is refused as `NO_PROVENANCE` whatever it contains. Nothing here is fetched: "
           "the system reads what was given to it.", ""]
    text = "\n".join(md)
    if write:
        with open(out_json if out_json is not None else OUT_DRY_RUN_JSON, "w",
                  encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        with open(out_md if out_md is not None else OUT_DRY_RUN_MD, "w",
                  encoding="utf-8") as fh:
            fh.write(text)
    return out, text
