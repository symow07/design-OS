"""Printed-data contract + completeness states (Phase 2A-6, §9–10).

Separates PRODUCT-FACING print data from internal task content. Only the
bounded, verified fields declared here may reach production artwork; task
titles, briefs, agent rationale and placeholder copy are structurally
excluded and additionally caught by a forbidden-copy validator.

Completeness states (§10) are per field:

    VERIFIED        real, human-supplied or record-sourced copy
    UNVERIFIED      present but from an unconfirmed source
    MISSING         required for this product class and absent
    PLACEHOLDER     present but placeholder language ("to be confirmed")
    NOT_APPLICABLE  legitimately absent for this product/market

Preview artwork may show clearly-marked non-production placeholders. The
production PDF and Gate 2 fail on MISSING, PLACEHOLDER, and materially
UNVERIFIED required fields — with a distinct code per failure kind, never
flattened into one generic error.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"
MISSING = "MISSING"
PLACEHOLDER = "PLACEHOLDER"
NOT_APPLICABLE = "NOT_APPLICABLE"

# Per-field failure codes (§10: never flatten into one generic failure).
CODE_MISSING = "REQUIRED_PRINT_FIELD_MISSING"
CODE_PLACEHOLDER = "PLACEHOLDER_PRINT_CONTENT"
CODE_UNVERIFIED = "UNVERIFIED_REQUIRED_PRINT_FIELD"
CODE_INTERNAL_TEXT = "INTERNAL_TEXT_IN_PRINT_DATA"
CODE_EXAMPLE_IDENTIFIER = "EXAMPLE_IDENTIFIER_IN_PRINT_DATA"
CODE_LEGAL_ROLE_MISSING = "REQUIRED_LEGAL_ROLE_MISSING"


@dataclass(frozen=True)
class PrintField:
    """One product-facing field in the print-data contract."""
    key: str
    label: str
    required: bool = False
    #: Legal-role block this field belongs to (§9). Required roles must be
    #: satisfied by at least one VERIFIED field.
    legal_role: str = ""
    max_len: int = 2000


#: THE bounded set of product-facing fields. Anything not listed here can
#: never populate production artwork.
PRINT_FIELDS: tuple[PrintField, ...] = (
    PrintField("brand_display_name", "Brand display name", required=True),
    PrintField("product_name", "Product-line name", required=True, max_len=120),
    PrintField("product_type", "Product type", required=True, max_len=120),
    PrintField("description", "Description"),
    PrintField("ingredients", "Approved INCI", required=True,
               legal_role="ingredients"),
    PrintField("how_to_use", "Directions", required=True),
    PrintField("warnings", "Warnings", required=True, legal_role="safety"),
    PrintField("net_weight", "Net content", required=True,
               legal_role="net_content", max_len=60),
    PrintField("shade", "Shade", max_len=60),
    PrintField("item_no", "Item / SKU", max_len=40),
    PrintField("barcode_ean", "Barcode", max_len=13),
    PrintField("qr_url", "QR", max_len=300),
    PrintField("batch_code", "Batch / date", max_len=60),
    PrintField("manufacturer", "Manufacturer", required=True,
               legal_role="manufacturer"),
    PrintField("marketer", "Marketer / exporter", legal_role="responsible_person"),
    PrintField("importer", "Importer / distributor",
               legal_role="responsible_person"),
    PrintField("country_of_origin", "Country of origin", required=True,
               legal_role="origin", max_len=80),
    # Free-text block carrying manufacturer/marketer/origin on legacy records.
    PrintField("regulatory_text", "Regulatory block"),
)

PRINT_FIELD_KEYS = tuple(f.key for f in PRINT_FIELDS)
_FIELDS_BY_KEY = {f.key: f for f in PRINT_FIELDS}

#: Legal roles that MUST be satisfied before production.
REQUIRED_LEGAL_ROLES = ("ingredients", "safety", "net_content",
                        "manufacturer", "origin")

#: Keys that are never product-facing — internal only. Present as a positive
#: guard: even if a caller injects one, it cannot enter the print record.
FORBIDDEN_SOURCE_KEYS = frozenset({
    "task_text", "task_title", "brief", "notes", "agent_rationale",
    "unresolved_questions", "prompt", "prompt_used", "direction_name",
    "worker_message", "reasoning",
})

_PLACEHOLDER_RE = re.compile(
    r"lorem ipsum|placeholder|\bTBD\b|\bTODO\b|to be confirmed|"
    r"to be determined|to be advised|coming soon|sample text|\bN/?A\b|"
    r"xxx+|\[[^\]]*\]|<[^>]*>|^\s*[-–—._]*\s*$",
    re.IGNORECASE,
)

#: Example/placeholder identifiers that must never print.
_EXAMPLE_BARCODES = frozenset({
    "0000000000000", "1234567890128", "1234567890123", "9999999999999",
    "5901234123457",           # the GS1 documentation example
})
_EXAMPLE_SKU_RE = re.compile(
    r"^(sku|item|code)?[-_ ]?(0+|1234|test|example|sample|demo|xxx)",
    re.IGNORECASE)

#: Phrases that mark internal/agent text leaking into print data.
_INTERNAL_MARKERS = (
    "create a new", "design a ", "redesign the", "project objective",
    "the brief", "task id", "prompt:", "direction:", "as an ai",
    "gate 1", "gate 2", "packaging structure:", "audience", "market:",
)


@dataclass
class FieldState:
    key: str
    label: str
    value: str
    state: str
    required: bool
    legal_role: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "state": self.state,
                "required": self.required, "legal_role": self.legal_role,
                "detail": self.detail, "has_value": bool(self.value.strip())}


@dataclass
class PrintDataRecord:
    """The verified printed-information record for one output."""
    fields: dict = field(default_factory=dict)          # key -> FieldState
    not_applicable: tuple = ()

    # --- views ----------------------------------------------------------

    def values(self) -> dict:
        """Only the values fit to print (VERIFIED / UNVERIFIED)."""
        return {k: fs.value for k, fs in self.fields.items()
                if fs.state in (VERIFIED, UNVERIFIED) and fs.value.strip()}

    def states(self) -> dict:
        return {k: fs.state for k, fs in self.fields.items()}

    def to_dict(self) -> dict:
        return {
            "fields": {k: fs.to_dict() for k, fs in self.fields.items()},
            "states": self.states(),
            "production_ready": self.production_ready,
            "failures": self.production_failures(),
        }

    @property
    def production_ready(self) -> bool:
        return not self.production_failures()

    def production_failures(self) -> list[dict]:
        """Per-field failures with DISTINCT codes (§10)."""
        out: list[dict] = []
        for key in PRINT_FIELD_KEYS:
            fs = self.fields.get(key)
            if fs is None or not fs.required:
                continue
            if fs.state == PLACEHOLDER:
                out.append({"code": CODE_PLACEHOLDER, "field": key,
                            "detail": f"{fs.label} carries placeholder text: "
                                      f"{fs.detail or fs.value[:60]!r}"})
            elif fs.state == MISSING:
                out.append({"code": CODE_MISSING, "field": key,
                            "detail": f"{fs.label} is required for production "
                                      "and is empty"})
            elif fs.state == UNVERIFIED:
                out.append({"code": CODE_UNVERIFIED, "field": key,
                            "detail": f"{fs.label} is present but unverified — "
                                      "a human must confirm it before print"})
        # identifier sanity, whatever their state
        for key, code, detail in self._identifier_failures():
            out.append({"code": code, "field": key, "detail": detail})
        # internal text anywhere in the record
        for key, fs in self.fields.items():
            if fs.value and _looks_internal(fs.value):
                out.append({"code": CODE_INTERNAL_TEXT, "field": key,
                            "detail": f"{fs.label} contains internal task or "
                                      "brief text, which must never print"})
        # legal-role coverage
        satisfied = {fs.legal_role for fs in self.fields.values()
                     if fs.legal_role and fs.state == VERIFIED}
        for role in REQUIRED_LEGAL_ROLES:
            if role not in satisfied and role not in self.not_applicable:
                out.append({"code": CODE_LEGAL_ROLE_MISSING, "field": role,
                            "detail": f"no verified field satisfies the "
                                      f"required legal role {role!r}"})
        return out

    def _identifier_failures(self):
        ean = (self.fields.get("barcode_ean").value
               if self.fields.get("barcode_ean") else "")
        digits = "".join(c for c in ean if c.isdigit())
        if digits and digits in _EXAMPLE_BARCODES:
            yield ("barcode_ean", CODE_EXAMPLE_IDENTIFIER,
                   "the barcode is a documentation/example EAN and must not print")
        elif digits and len(digits) not in (0, 8, 12, 13):
            yield ("barcode_ean", CODE_EXAMPLE_IDENTIFIER,
                   f"barcode {digits!r} is not a valid EAN-8/12/13 length")
        sku = (self.fields.get("item_no").value
               if self.fields.get("item_no") else "")
        if sku and _EXAMPLE_SKU_RE.match(sku.strip()):
            yield ("item_no", CODE_EXAMPLE_IDENTIFIER,
                   f"item/SKU {sku!r} looks like an example placeholder")


def _looks_internal(value: str) -> bool:
    low = value.lower()
    return any(marker in low for marker in _INTERNAL_MARKERS)


def classify_value(fld: PrintField, value, verified: bool) -> FieldState:
    text = (value or "") if isinstance(value, str) else str(value or "")
    text = text.strip()[: fld.max_len]
    if not text:
        state, detail = (MISSING if fld.required else NOT_APPLICABLE), ""
    elif _PLACEHOLDER_RE.search(text):
        match = _PLACEHOLDER_RE.search(text)
        state, detail = PLACEHOLDER, match.group(0)
    elif verified:
        state, detail = VERIFIED, ""
    else:
        state, detail = UNVERIFIED, "source not confirmed"
    return FieldState(key=fld.key, label=fld.label, value=text, state=state,
                      required=fld.required, legal_role=fld.legal_role,
                      detail=detail)


def build_print_record(source: dict | None, *, verified_keys=None,
                       not_applicable=()) -> PrintDataRecord:
    """Build the record from a bounded source mapping.

    Unknown and internal keys are DROPPED (never merely flagged): the record
    is a whitelist, so internal text has no path into production artwork.
    ``verified_keys`` names the fields whose provenance a human confirmed;
    everything else present is UNVERIFIED.
    """
    source = source or {}
    verified_keys = set(verified_keys or ())
    fields = {}
    for fld in PRINT_FIELDS:
        fields[fld.key] = classify_value(
            fld, source.get(fld.key), verified=fld.key in verified_keys)
    return PrintDataRecord(fields=fields, not_applicable=tuple(not_applicable))


def panel_info_from_record(record: PrintDataRecord, *, allow_preview=False) -> dict:
    """The dict the exporters render.

    Production (``allow_preview=False``): only printable values. Preview
    (``allow_preview=True``): placeholders pass through, clearly marked, so
    the reviewer can see what is still outstanding — such a document is never
    a production deliverable.
    """
    out = {}
    for key, fs in record.fields.items():
        if fs.state in (VERIFIED, UNVERIFIED) and fs.value:
            out[key] = fs.value
        elif allow_preview and fs.state == PLACEHOLDER and fs.value:
            out[key] = f"[UNAPPROVED PREVIEW] {fs.value}"
    return out


def forbidden_copy_strings(task) -> tuple[str, ...]:
    """Strings that must never appear on consumer panels for this task."""
    out = []
    text = (getattr(task, "task_text", "") or "").strip()
    if text:
        out.append(text)
        first = text.splitlines()[0].strip()
        if len(first) >= 12:
            out.append(first)
    brief = getattr(task, "brief", None)
    for attr in ("design_intent",):
        doc = getattr(brief, attr, None) if brief else None
        if isinstance(doc, dict):
            for value in doc.values():
                if isinstance(value, str) and len(value) >= 24:
                    out.append(value)
    product = getattr(task, "product", None)
    pname = (getattr(product, "name", "") or "").strip().lower()
    return tuple(s for s in dict.fromkeys(out) if s.strip().lower() != pname)


__all__ = [
    "VERIFIED", "UNVERIFIED", "MISSING", "PLACEHOLDER", "NOT_APPLICABLE",
    "CODE_MISSING", "CODE_PLACEHOLDER", "CODE_UNVERIFIED",
    "CODE_INTERNAL_TEXT", "CODE_EXAMPLE_IDENTIFIER", "CODE_LEGAL_ROLE_MISSING",
    "PRINT_FIELDS", "PRINT_FIELD_KEYS", "REQUIRED_LEGAL_ROLES",
    "PrintDataRecord", "FieldState",
    "build_print_record", "panel_info_from_record", "forbidden_copy_strings",
]
