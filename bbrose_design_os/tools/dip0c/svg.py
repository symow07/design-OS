"""Native SVG audit (DIP-0C1).

SVG is XML, not a PDF. It is parsed natively with a *hardened* expat pass — not
via PyMuPDF — and the parser is the security gate the plan requires:

* external entity resolution is blocked (`ExternalEntityRefHandler` → 0, and
  parameter-entity parsing set to NEVER): no network/file fetch ever happens;
* an internal `<!ENTITY>` subset (the billion-laughs vector) is flagged unsafe;
* `<script>`, `on*` event-handler attributes, `javascript:` URIs, remote
  `href`/`xlink:href`, and `<foreignObject>` are detected and make the file
  unsafe to ingest.

An external DOCTYPE alone (old Adobe SVGs) is recorded but not fatal — the fetch
is blocked regardless. No renderer runs in C1; previews are deferred. Native
structure, security findings and (future) rendered preview are kept distinct.
"""
from __future__ import annotations

from pathlib import Path
from xml.parsers import expat

from tools.dip0.provenance import Inferred

from . import config as C

PARSER = f"{C.TOOL_NAME}.svg/{C.TOOL_VERSION}+expat"

MAX_BYTES = 32 * 1024 * 1024        # refuse pathologically large SVG
_VECTOR_TAGS = ("path", "rect", "circle", "ellipse", "polygon", "polyline", "line")
_REMOTE_SCHEMES = ("http://", "https://", "ftp://", "file://", "//")


def _inf(value, tier, source, evidence, confidence):
    d = Inferred(value=value, source=source, evidence=list(evidence),
                 confidence=round(confidence, 3), parser=PARSER).to_dict()
    d["tier"] = tier
    return d


class _Rejected(Exception):
    """Raised to stop parsing when an unrecoverable unsafe construct appears."""


class _SvgScan:
    def __init__(self):
        self.tag_counts: dict[str, int] = {}
        self.fills = 0
        self.strokes = 0
        self.gradients = 0
        self.masks = 0
        self.clip_paths = 0
        self.text_nodes = 0
        self.image_nodes = 0
        self.image_remote = 0
        self.image_data_uri = 0
        self.use_refs = 0
        self.filters = 0
        self.namespaces: set[str] = set()
        self.view_box = None
        self.width = None
        self.height = None
        # security findings
        self.scripts = 0
        self.event_handlers = 0
        self.js_uris = 0
        self.remote_refs = 0
        self.foreign_objects = 0
        self.external_entity_attempts = 0
        self.internal_entities = 0
        self.has_doctype = False
        self.external_dtd = None

    # --- expat handlers ----------------------------------------------------
    def start_element(self, name, attrs):
        local = name.rsplit("}", 1)[-1].rsplit(":", 1)[-1].lower()
        self.tag_counts[local] = self.tag_counts.get(local, 0) + 1
        if local in _VECTOR_TAGS or local == "path":
            pass
        if local == "script":
            self.scripts += 1
        elif local == "foreignobject":
            self.foreign_objects += 1
        elif local == "text" or local == "tspan":
            self.text_nodes += 1
        elif local == "image":
            self.image_nodes += 1
        elif local == "use":
            self.use_refs += 1
        elif local in ("lineargradient", "radialgradient"):
            self.gradients += 1
        elif local == "mask":
            self.masks += 1
        elif local == "clippath":
            self.clip_paths += 1
        elif local == "filter":
            self.filters += 1
        elif local == "svg":
            self.view_box = attrs.get("viewBox") or self.view_box
            self.width = attrs.get("width") or self.width
            self.height = attrs.get("height") or self.height

        for k, v in attrs.items():
            kl = k.rsplit("}", 1)[-1].rsplit(":", 1)[-1].lower()
            if kl.startswith("on"):
                self.event_handlers += 1
            if kl == "fill" and v not in ("none", ""):
                self.fills += 1
            if kl == "stroke" and v not in ("none", ""):
                self.strokes += 1
            val = (v or "").strip()
            low = val.lower()
            if low.startswith("javascript:"):
                self.js_uris += 1
            if kl in ("href", "xlink:href", "href"):
                self._classify_href(local, low)
            elif "url(" in low and any(s in low for s in _REMOTE_SCHEMES):
                self.remote_refs += 1
            if k.startswith("xmlns"):
                self.namespaces.add(val)

    def _classify_href(self, local, low):
        if low.startswith("data:"):
            if local == "image":
                self.image_data_uri += 1
            return
        if low.startswith("#"):
            return  # internal fragment reference — safe
        if any(low.startswith(s) for s in _REMOTE_SCHEMES) or ":" in low[:12]:
            self.remote_refs += 1
            if local == "image":
                self.image_remote += 1
        elif local == "image":
            self.image_remote += 1   # relative external file ref

    def doctype(self, name, sysid, pubid, has_internal_subset):
        self.has_doctype = True
        if sysid or pubid:
            self.external_dtd = {"sysid": sysid, "pubid": pubid}

    def entity_decl(self, name, is_param, value, base, sysid, pubid, notation):
        # any <!ENTITY> declaration — internal entity subset (billion-laughs)
        self.internal_entities += 1
        raise _Rejected("internal entity declaration")

    def external_entity_ref(self, context, base, sysid, pubid):
        self.external_entity_attempts += 1
        return 0  # NEVER resolve — no network / no file fetch


def audit(rel_path: str) -> dict:
    full = C.physical_path(rel_path, C.REPO_ROOT)
    size = full.stat().st_size
    if size > MAX_BYTES:
        return {"format": ".svg", "parser": PARSER,
                "parse_status": "REJECTED_TOO_LARGE",
                "size_bytes": size,
                "security": _security_block(unsafe=True,
                                            reasons=[f"{size} bytes > {MAX_BYTES}"]),
                "technical_readiness": _inf(C.READY_QUARANTINE, C.TIER_HEURISTIC,
                                            "too_large", ["exceeds size guard"], 0.6)}

    data = full.read_bytes()
    scan = _SvgScan()
    p = expat.ParserCreate()
    p.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    p.StartElementHandler = scan.start_element
    p.StartDoctypeDeclHandler = scan.doctype
    p.EntityDeclHandler = scan.entity_decl
    p.ExternalEntityRefHandler = scan.external_entity_ref

    parse_status = "PARSED"
    parse_error = None
    try:
        p.Parse(data, True)
    except _Rejected as e:
        parse_status = "REJECTED_UNSAFE_XML"
        parse_error = str(e)
    except expat.ExpatError as e:
        parse_status = "MALFORMED_XML"
        parse_error = f"{type(e).__name__}: {e}"

    reasons = []
    if scan.scripts:
        reasons.append(f"{scan.scripts} <script> node(s)")
    if scan.event_handlers:
        reasons.append(f"{scan.event_handlers} on* event-handler attr(s)")
    if scan.js_uris:
        reasons.append(f"{scan.js_uris} javascript: URI(s)")
    if scan.remote_refs:
        reasons.append(f"{scan.remote_refs} remote/external reference(s)")
    if scan.foreign_objects:
        reasons.append(f"{scan.foreign_objects} <foreignObject> node(s)")
    if scan.internal_entities:
        reasons.append("internal <!ENTITY> subset (entity-expansion vector)")
    if scan.external_entity_attempts:
        reasons.append(f"{scan.external_entity_attempts} external-entity ref "
                       "(blocked, not resolved)")
    unsafe = bool(reasons) or parse_status == "REJECTED_UNSAFE_XML"

    vector_paths = sum(scan.tag_counts.get(t, 0) for t in _VECTOR_TAGS)
    return {
        "format": ".svg",
        "parser": PARSER,
        "size_bytes": size,
        "parse_status": parse_status,
        "parse_error": parse_error,
        "view_box": scan.view_box,
        "declared_size": {"width": scan.width, "height": scan.height},
        "element_counts": dict(sorted(scan.tag_counts.items())),
        "vector_paths": _inf(vector_paths, C.TIER_DIRECT, "svg_shape_tags",
                             [f"{vector_paths} path/rect/circle/… nodes"], 1.0),
        "fills": scan.fills, "strokes": scan.strokes,
        "gradients": scan.gradients, "masks": scan.masks,
        "clip_paths": scan.clip_paths, "filters": scan.filters,
        "text_nodes": scan.text_nodes, "use_refs": scan.use_refs,
        "raster": {"image_nodes": scan.image_nodes,
                   "embedded_data_uri": scan.image_data_uri,
                   "remote_or_external": scan.image_remote},
        "namespaces": sorted(scan.namespaces),
        "doctype": {"present": scan.has_doctype, "external_dtd": scan.external_dtd},
        "security": _security_block(unsafe, reasons),
        "technical_readiness": _readiness(unsafe, parse_status, vector_paths,
                                          scan.image_nodes),
    }


def _security_block(unsafe: bool, reasons: list[str]) -> dict:
    return {
        "safe_to_ingest": _inf(not unsafe, C.TIER_HEURISTIC, "svg_security_scan",
                               reasons or ["no unsafe constructs detected"],
                               0.85 if reasons else 0.7),
        "network_access": "blocked",           # external entities never resolved
        "script_execution": "not_executed",    # never rendered/executed in C1
        "findings": reasons,
        "human_review_required": bool(unsafe),
    }


def _readiness(unsafe, parse_status, vector_paths, image_nodes):
    if unsafe:
        return _inf(C.READY_QUARANTINE, C.TIER_HEURISTIC, "svg_unsafe",
                    ["unsafe XML/script/remote content; quarantine until reviewed"],
                    0.7)
    if parse_status == "MALFORMED_XML":
        return _inf(C.READY_REJECT_CANDIDATE, C.TIER_HEURISTIC, "svg_malformed",
                    ["SVG did not parse as XML"], 0.6)
    if vector_paths == 0 and image_nodes > 0:
        return _inf(C.READY_NEEDS_VECTOR_RECONSTRUCTION, C.TIER_HEURISTIC,
                    "raster_only_svg",
                    ["SVG wraps raster image(s), no native vector geometry"], 0.65)
    if vector_paths == 0:
        return _inf(C.READY_REFERENCE_ONLY, C.TIER_HEURISTIC, "empty_svg",
                    ["no vector geometry found"], 0.5)
    return _inf(C.readiness_value(C.READY_TECHNICALLY_USABLE_WITH_CAVEATS),
                C.TIER_HEURISTIC, "clean_svg",
                ["native vector SVG geometry"], 0.6)
