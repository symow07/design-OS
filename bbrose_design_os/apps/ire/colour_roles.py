"""The colour-role layer — §BH39(e), in the idiom of ``font_roles`` (§BH32).

brand_gov FIRST (§BH39(b)): a role with a brand colour resolves to it and takes no
library candidate; a role without one may take a PRODUCTION-palette candidate;
REFERENCE palettes are inspiration only and never written into an output. The
layer never invents a value: every candidate is a row of a governed source, and a
role's fallback is the surface's OWN literal (the value the engine draws today),
so an artefact cannot draw a colour the record cannot name.

Exemption (§BH32(h), carried to colour by §BH39(e)): an exempt / anonymous /
untagged document resolves EXACTLY as today — ``resolve_role`` hands back the
surface's fallback untouched. Only a document tagged with a non-exempt surface
(``font_roles.SURFACE_KEY``) reads brand_gov through the layer.

The M7 emitter's substrate record and the PALT powder engine's shade authority
are not clients of this layer and are untouched by it.
"""
from __future__ import annotations

import json
from pathlib import Path

from apps.ire.font_roles import is_exempt, surface_of, SURFACE_KEY, NON_EXEMPT_EXERCISE  # noqa: F401

SCHEMA = "colour_roles/1.0"
USAGE_SCHEMA = "colour_usage/1.0"
RECORD_PATH = Path(__file__).resolve().parents[2] / "docs" / "brand_gov" / "colour_roles_1_0.json"

#: the eight roles of §BH39(a), in the record's order
ROLES = ("ground_cream", "ground_gold", "ground_blush", "accent_light",
         "accent_blush", "accent_nude", "accent_dark", "ink")

#: sources a resolved colour names — the record row carries exactly one
SOURCE_BRAND_GOV = "BRAND_GOV"                 # a ColorSystem swatch (the authority)
SOURCE_PRODUCTION_PALETTE = "PRODUCTION_PALETTE"  # a library colour of a PRODUCTION row (only where no brand colour)
SOURCE_SURFACE_FALLBACK = "SURFACE_FALLBACK"   # the surface's own literal (exempt, or nothing governed)
SOURCE_PROCESS = "PROCESS"                     # white / black / die colours: process, not brand

#: verdicts a library candidate receives
CANDIDATE_ADMITTED = "ADMITTED"                      # a PRODUCTION row's colour, role has no brand colour
CANDIDATE_INSPIRATION_ONLY = "INSPIRATION_ONLY"      # a REFERENCE row's colour: surfaced, never written
CANDIDATE_REFUSED_ROLE_HAS_BRAND_COLOUR = "REFUSED_ROLE_HAS_BRAND_COLOUR"
CANDIDATE_REFUSED_NOT_PRODUCTION = "REFUSED_NOT_PRODUCTION"

REFUSAL_UNGOVERNED_DEFAULT = "COLOUR_OUTSIDE_BRAND_GOV_AND_PRODUCTION_PALETTE"

_RECORD: dict | None = None


def record() -> dict:
    """The tracked brand_colour_roles/1.0 record (docs/brand_gov)."""
    global _RECORD
    if _RECORD is None:
        _RECORD = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    return _RECORD


def reset_cache() -> None:
    global _RECORD
    _RECORD = None


def role_entry(role: str) -> dict:
    for r in record()["roles"]:
        if r["role"] == role:
            return r
    raise KeyError(role)


def brand_swatch(role: str) -> dict | None:
    """The brand_gov swatch a role maps to — {system_id, name, hex} — or None
    (a role with no brand colour: accent_dark, ink)."""
    return role_entry(role).get("brand_swatch") or None


def live_brand_hex(swatch: dict) -> str | None:
    """The swatch's hex in the LIVE ColorSystem record when a database is at
    hand (the authority proper); None when no canonical system carries it.
    Read-only; never writes."""
    try:
        from apps.core.models import ColorSystem, STATUS_CANONICAL
        for cs in ColorSystem.objects.filter(status=STATUS_CANONICAL, system_id=swatch["system_id"]):
            for sw in cs.palette or []:
                if isinstance(sw, dict) and sw.get("name") == swatch["name"] and sw.get("hex"):
                    return str(sw["hex"]).upper()
    except Exception:  # noqa: BLE001 — no database, no app registry: the record stands
        return None
    return None


def _color(hex_value: str, cmyk=None):
    from apps.ire.graph import Color
    return Color.from_hex(hex_value, cmyk=cmyk)


def library_candidate(role: str, hex_value: str, tier_row: dict) -> dict:
    """§BH39(b): a library colour's verdict for a role. The seam is the tier
    record's row for the file the colour was read from: only a PRODUCTION row
    may be ADMITTED, and only for a role with no brand colour."""
    tier = str((tier_row or {}).get("tier") or "")
    if tier != "PRODUCTION":
        verdict = CANDIDATE_INSPIRATION_ONLY if tier == "REFERENCE" else CANDIDATE_REFUSED_NOT_PRODUCTION
    elif brand_swatch(role) is not None:
        verdict = CANDIDATE_REFUSED_ROLE_HAS_BRAND_COLOUR
    else:
        verdict = CANDIDATE_ADMITTED
    return {"role": role, "hex": hex_value.upper(), "tier": tier or None, "verdict": verdict,
            "sha256": (tier_row or {}).get("sha256"), "relative_path": (tier_row or {}).get("relative_path"),
            "evidence": (tier_row or {}).get("evidence")}


def resolve_role(doc_or_metadata, role: str, fallback, *, candidates=()) -> dict:
    """Resolve ONE role for a document. Returns the record row:
    {role, hex, cmyk, source, tier, evidence, verdicts}; ``row["color"]`` is the
    Color to draw. Exempt documents get the fallback untouched (byte-identical
    surfaces). Non-exempt: brand_gov FIRST; then an ADMITTED library candidate;
    then the surface's fallback (a literal of the code, recorded as such)."""
    if role not in ROLES:
        raise ValueError(f"unknown colour role {role!r}; the roles are {ROLES}")
    if is_exempt(doc_or_metadata):
        return {"role": role, "hex": fallback.to_hex().upper(),
                "color": fallback, "source": SOURCE_SURFACE_FALLBACK, "tier": None,
                "evidence": "exempt surface — resolves as today", "verdicts": []}
    sw = brand_swatch(role)
    verdicts = [library_candidate(role, c[0], c[1]) for c in candidates]
    if sw is not None:
        live = live_brand_hex(sw)
        hex_value = (live or sw["hex"]).upper()
        return {"role": role, "hex": hex_value, "color": _color(hex_value), "source": SOURCE_BRAND_GOV,
                "tier": None, "evidence": f'brand_gov {sw["system_id"]} / {sw["name"]}'
                + (" (live record)" if live else " (tracked record; no live system carried it)"),
                "verdicts": verdicts}
    admitted = next((v for v in verdicts if v["verdict"] == CANDIDATE_ADMITTED), None)
    if admitted is not None:
        return {"role": role, "hex": admitted["hex"], "color": _color(admitted["hex"]),
                "source": SOURCE_PRODUCTION_PALETTE, "tier": "PRODUCTION",
                "evidence": admitted["evidence"], "verdicts": verdicts}
    return {"role": role, "hex": fallback.to_hex().upper(),
            "color": fallback, "source": SOURCE_SURFACE_FALLBACK, "tier": None,
            "evidence": "no brand colour and no admitted candidate — the surface's own literal",
            "verdicts": verdicts}


# ---- usage (§BH39(f)) ---------------------------------------------------------

def usage_record(rows: list[dict]) -> dict:
    """colour_usage/1.0 — per document, the resolved rows and a per-colour
    counter of the nodes drawn with each; the emitter reconciles it against
    every place the artefact applies colour (``reconcile_colours``)."""
    counter: dict[str, int] = {}
    for r in rows:
        for _ in r.get("nodes") or ():
            counter[r["hex"]] = counter.get(r["hex"], 0) + 1
    return {"schema_version": USAGE_SCHEMA, "rows": [{k: v for k, v in r.items() if k != "color"} for r in rows],
            "counter": counter}


# ---- reconciliation (§BH39(f), widened by §BH50(f)(7)) ------------------------------------------------------------

#: §BH50(f)(7), OWNER RULED 2026-09-13: "THE COUNTER READS EVERY PLACE COLOUR IS APPLIED — fills, strokes and
#: text. A counter that reads fills alone is not a counter, and the ink proved it." Before this, the reader here
#: (``reconcile_fills``) opened the artefact with PyMuPDF and kept ``get_drawings()``' fills alone: on the final
#: task-52 render the ink #2A2426, applied as 38 strokes and 47 text shows, and the status colour #8E4F5C, applied
#: as text, both read "counted but absent" from a page that carried them. The reader is now
#: ``colour_applications.read_applications`` — the artefact's content stream, operator by operator (reportlab's
#: grammar is the only writer) — and the verdict compares the SET of colours applied on the page (fills, strokes,
#: text shown in a render mode that applies colour, and the stops of every shading) with the SET the emitter
#: counted (colour-set calls, plus gradient stops drawn), BOTH WAYS. A colour is matched in the colour space it is
#: DRAWN in: DeviceRGB and DeviceGray by hex, DeviceCMYK by components against the counted rows' own cmyk — never
#: through an ICC conversion, which is what PyMuPDF hands back for a CMYK fill and what reads a jar's CMYK motif as
#: a false disagreement. Process white and black are decided on components. Images are colour applied to the page
#: and are NOT colour-reconciled — placement_usage/1.0 governs them — and the record says so. The sub-record is
#: versioned so a shape persisted by the fills-only reader (no schema_version) is told apart from this one
#: without moving the outer key. Latent and out of this write set: a literal whose float channels round differently
#: at the decimals reportlab writes (the 0.55 tint) — unreachable on the live path, where every colour is built
#: from a hex. A second known limit, older than this reader and recorded rather than widened here: an RGB shading
#: draws each stop's LITERAL (pdf_ai._paint_gradient bypasses the role layer on that branch) and the stops counter
#: counts that same literal, so were a declared role's brand hex ever to differ from the composer's literal, the
#: stops would print the literal and still reconcile. On task 52 both role rows are BRAND_GOV with hex equal to the
#: declared literal, so nothing diverges today; resolving RGB stops through the layer is a drawing change, his.
RECONCILIATION_SCHEMA = "colour_reconciliation/2.0"
RECONCILED = "RECONCILED"                    # the artefact was read; agree is True or False
UNREAD = "UNREAD"                            # the artefact could not be read: unmeasured, never passed
EXEMPT_NOT_COUNTED = "EXEMPT_NOT_COUNTED"    # an exempt document draws literals and counts nothing (§BH32(h))
NOT_EMITTED = "NOT_EMITTED"                  # no artefact was written (withheld): unmeasured
COLOUR_USAGE_DISAGREEMENT_CODE = "COLOUR_USAGE_ARTEFACT_DISAGREEMENT"
COLOUR_USAGE_UNRECONCILED_CODE = "COLOUR_USAGE_UNRECONCILED"
PROCESS_HEXES = ("#FFFFFF", "#000000")
_PROCESS_CMYK = ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
_CMYK_TOLERANCE = 5e-4
READER = "apps/ire/colour_applications.read_applications — the content stream, operator by operator"
UNITS = {"counter": "colour-set calls (one per resolved colour set, a CMYK shading's stops among them) and the "
                    "stops of RGB shadings drawn",
         "artefact": "paint operations (fills, strokes, text shows) and shading-function stop endpoints"}


def _cmyk_close(a, b) -> bool:
    return len(a) == len(b) == 4 and all(abs(float(x) - float(y)) <= _CMYK_TOLERANCE for x, y in zip(a, b))


def _artefact_key(event: dict, cmyk_of: dict) -> tuple:
    """The key an application is compared under, and the counted hex a CMYK
    application matched (None when it matched nothing). RGB and Gray: the hex
    as drawn. CMYK: process on components, else the counted row whose cmyk it
    is drawn in, else the components themselves — a key no counter holds, so
    an unmatched CMYK application can never pass by coincidence."""
    if event.get("hex"):
        return event["hex"], None
    comps = tuple(float(x) for x in event.get("components") or ())
    if event.get("space") == "DeviceCMYK" and len(comps) == 4:
        if _cmyk_close(comps, _PROCESS_CMYK[0]):
            return "#FFFFFF", "#FFFFFF"
        if _cmyk_close(comps, _PROCESS_CMYK[1]):
            return "#000000", "#000000"
        for hex_value, cmyk in cmyk_of.items():
            if _cmyk_close(comps, cmyk):
                return hex_value, hex_value
        return "DeviceCMYK(%s)" % ",".join(f"{c:g}" for c in comps), None
    return "%s(%s)" % (event.get("space"), ",".join(f"{float(c):g}" for c in comps)), None


def _unmeasured(status: str, reason: str, **fields) -> dict:
    return {"schema_version": RECONCILIATION_SCHEMA, "status": status, "reader": READER, "units": UNITS,
            "reason": reason, "agree": None,
            "codes": [] if status == EXEMPT_NOT_COUNTED else [COLOUR_USAGE_UNRECONCILED_CODE], **fields}


def reconcile_colours(pdf_path: str, usage: dict) -> dict:
    """Read the emitted artefact back — every place colour is applied — and
    reconcile it against the counter, both ways. Never raises: an artefact this
    reader cannot read is UNREAD with its reason and the unreconciled code,
    which is unmeasured and never a pass; an exempt document, which counts
    nothing, is EXEMPT_NOT_COUNTED with ``agree`` None."""
    from apps.ire import colour_applications as CA
    if usage.get("exempt"):
        return _unmeasured(EXEMPT_NOT_COUNTED, "an exempt document draws its literals and counts nothing "
                           "(§BH32(h)); there is no counter to reconcile")
    read = CA.read_applications(pdf_path)
    if read.get("status") != "READ":
        return _unmeasured(UNREAD, str(read.get("reason")))
    counter = {str(k).upper(): int(v) for k, v in (usage.get("counter") or {}).items()}
    stops_counted = {str(k).upper(): int(v) for k, v in (usage.get("gradient_stops") or {}).items()}
    cmyk_of = {str(r.get("hex")).upper(): tuple(float(x) for x in r["cmyk"])
               for r in usage.get("rows") or () if r.get("cmyk")}
    counted = set(counter) | set(stops_counted)
    applied: dict = {kind: {} for kind in ("fill", "stroke", "text", "text_stroke", "stop")}
    applied_cmyk: list = []
    images = 0
    unreadable = []          # a shading function or an XObject this reader cannot read
    for ev in read["events"]:
        kind = ev.get("kind")
        if kind == "image":
            images += 1
            continue
        if ev.get("unreadable"):
            unreadable.append(f"{kind} {ev.get('shading') or ev.get('xobject')}")
            continue
        key, matched = _artefact_key(ev, cmyk_of)
        applied[kind][key] = applied[kind].get(key, 0) + 1
        if ev.get("space") == "DeviceCMYK":
            comps = [float(x) for x in ev.get("components") or ()]
            entry = next((e for e in applied_cmyk if e["components"] == comps and e["kind"] == kind), None)
            if entry is None:
                applied_cmyk.append({"kind": kind, "components": comps, "matched_hex": matched, "count": 1})
            else:
                entry["count"] += 1
    if unreadable:
        return _unmeasured(UNREAD, "an object this reader cannot read: %s" % ", ".join(unreadable),
                           applied={k: dict(sorted(v.items())) for k, v in applied.items()}, images=images)
    on_page = set().union(*(set(v) for v in applied.values()))
    process = sorted(h for h in on_page if h in PROCESS_HEXES)
    applied_not_counted = sorted(h for h in on_page if h not in counted and h not in PROCESS_HEXES)
    counted_not_applied = sorted(h for h in counted if h not in on_page)
    agree = not applied_not_counted and not counted_not_applied
    return {"schema_version": RECONCILIATION_SCHEMA, "status": RECONCILED, "reader": READER, "units": UNITS,
            "applied": {k: dict(sorted(v.items())) for k, v in applied.items()},
            "applied_cmyk": applied_cmyk,
            "images": {"count": images,
                       "note": "colour applied as an image is not colour-reconciled; placement_usage/1.0 governs it"},
            "counted": {"colour_set_calls": dict(sorted(counter.items())),
                        "gradient_stops": dict(sorted(stops_counted.items()))},
            "process": process,
            "applied_not_counted": applied_not_counted, "counted_not_applied": counted_not_applied,
            "agree": agree, "codes": [] if agree else [COLOUR_USAGE_DISAGREEMENT_CODE]}


__all__ = ["SCHEMA", "USAGE_SCHEMA", "RECORD_PATH", "ROLES", "record", "reset_cache", "role_entry", "brand_swatch",
           "live_brand_hex", "library_candidate", "resolve_role", "usage_record", "reconcile_colours",
           "RECONCILIATION_SCHEMA", "RECONCILED", "UNREAD", "EXEMPT_NOT_COUNTED", "NOT_EMITTED",
           "COLOUR_USAGE_DISAGREEMENT_CODE", "COLOUR_USAGE_UNRECONCILED_CODE", "PROCESS_HEXES",
           "SOURCE_BRAND_GOV", "SOURCE_PRODUCTION_PALETTE", "SOURCE_SURFACE_FALLBACK", "SOURCE_PROCESS",
           "CANDIDATE_ADMITTED", "CANDIDATE_INSPIRATION_ONLY", "CANDIDATE_REFUSED_ROLE_HAS_BRAND_COLOUR",
           "CANDIDATE_REFUSED_NOT_PRODUCTION", "REFUSAL_UNGOVERNED_DEFAULT", "ROLE_MAP_KEY", "declare_roles", "role_map",
           "resolve_fill", "brand_hexes_for_check", "compose_goal_exercise"]


# ---- the document's role map (the composer's declaration) and the emitter's resolution ----

#: ``doc.metadata[ROLE_MAP_KEY]`` = {"<#RRGGBB literal the composer used>": "<role>"} — the composer declares which
#: of its literals are colour ROLES; the emitter resolves those through the layer for a NON-exempt document and
#: draws every other colour as the literal it is. Exempt surfaces never declare one and are byte-identical to today.
ROLE_MAP_KEY = "colour_roles/1.0"


def declare_roles(doc, mapping: dict) -> None:
    bad = [r for r in mapping.values() if r not in ROLES]
    if bad:
        raise ValueError(f"unknown colour roles {bad}; the roles are {ROLES}")
    doc.metadata = dict(doc.metadata or {}, **{ROLE_MAP_KEY: {k.upper(): v for k, v in mapping.items()}})


def role_map(doc_or_metadata) -> dict:
    md = doc_or_metadata if isinstance(doc_or_metadata, dict) else (getattr(doc_or_metadata, "metadata", None) or {})
    return dict(md.get(ROLE_MAP_KEY) or {})


def resolve_fill(doc_or_metadata, color, *, cache: dict | None = None):
    """The emitter's call: the Color to DRAW for ``color`` on this document and
    the record row that explains it. A non-exempt document whose role map names
    the colour's hex resolves it through ``resolve_role``; everything else is
    the literal (row.source = SURFACE_FALLBACK or PROCESS)."""
    hex_value = color.to_hex().upper()
    if cache is not None and hex_value in cache:
        return cache[hex_value]
    mapping = role_map(doc_or_metadata)
    role = mapping.get(hex_value)
    if role is None or is_exempt(doc_or_metadata):
        row = {"role": None, "hex": hex_value, "color": color,
               "source": SOURCE_PROCESS if hex_value in ("#FFFFFF", "#000000") else SOURCE_SURFACE_FALLBACK,
               "tier": None, "evidence": "literal", "verdicts": []}
    else:
        row = resolve_role(doc_or_metadata, role, color)
        row["declared_hex"] = hex_value
    if cache is not None:
        cache[hex_value] = row
    return row


def brand_hexes_for_check(brand_id=None) -> list[str]:
    """§BH39(e): what the post-hoc palette check measures against — the LAYER's
    roles (their brand swatches, Warm Gold included), brand_gov FIRST. The
    prompt path keeps its seeded palettes; this is the check's vocabulary."""
    out = []
    for r in record()["roles"]:
        sw = r.get("brand_swatch")
        if sw and sw.get("hex"):
            h = (live_brand_hex(sw) or sw["hex"]).upper()
            if h not in out:
                out.append(h)
    return out


def compose_goal_exercise():
    """§BH39 goal state: a REAL non-exempt document — one field per colour role
    and a live text line — every role declared in its role map so the emitter
    resolves each through the layer to brand_gov (Warm Gold included)."""
    from apps.ire.graph import Color, Document, Group, Rect, SolidFill, TextRun
    lit = {  # the design language's own literals for the roles it draws today; a role with no literal uses its measured hex
        "ground_cream": "#FAF3EC", "ground_gold": "#CBA87D", "ground_blush": "#F2C4CE", "accent_light": "#FDFBF7",
        "accent_blush": "#F7DDE3", "accent_nude": "#E8C9B3", "accent_dark": "#231916", "ink": "#000000",
    }
    kids = []
    for i, role in enumerate(ROLES):
        kids.append(Rect(name=f"field-{role}", x=4.0 + i * 11.0, y=6.0, w=10.0, h=26.0, fill=SolidFill(color=Color.from_hex(lit[role]))))
    kids.append(TextRun(name="ink-line", text="BBROSE colour roles — goal exercise", x=4, y=40, font="regular", size_pt=7,
                        color=Color.from_hex(lit["ink"])))
    doc = Document(title="colour roles goal exercise", page_w=96, page_h=48, root=Group(name="root", children=kids))
    doc.metadata = {SURFACE_KEY: NON_EXEMPT_EXERCISE}
    declare_roles(doc, {v: k for k, v in lit.items()})
    return doc
