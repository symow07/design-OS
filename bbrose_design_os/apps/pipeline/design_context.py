"""Read-only DIP context adapter — Phase 2A-3 (`design_intelligence_context/1.0`).

Gives the Creative Director bounded institutional context — what the house has made, what
conventions recur, which references exist — WITHOUT reusing anything. The adapter reads the
existing lexical intelligence search and produces text-only descriptive summaries; it never
supplies an asset, a font file, a layout to copy, or a permission.

Boundaries, each carried by code rather than by promise:

* **Read-only.** The only data source is `build_search_query`/`execute_search`
  (reviewer-candidate semantics, lexical ranking). No semantic search, no OpenAI, no second
  search implementation, no legacy DesignReference authority, and no write of any kind.
* **Authorization is the caller's identity, never the brief's.** The actor comes from the
  design workflow. An unauthorized actor gets an EMPTY context with a bounded reason, and
  design generation continues without DIP context; authorization is never bypassed and
  never fails the creative workflow.

  §BH58(d) SPLIT THE CAPABILITY. This read was checked against
  `VIEW_INTELLIGENCE_REVIEW_QUEUE`, "the same action gating the search view" — so reading
  the house library to inform a design required being an enabled REVIEWER. Measured: every
  run of the owner's brief logged `DENIED:REVIEWER_DISABLED`, and his account holds no
  active role either, so the context has been empty on every run since the system existed.
  The owner: "Reading the house library to inform a design is not reviewing evidence, and a
  background job is not a person … Do not grant my account a reviewer role to make a
  machine able to read my own library." It is now checked as
  `READ_DESIGN_INTELLIGENCE_CONTEXT` via `authorize_pipeline_read`, which requires an
  authenticated, active actor and NOTHING about review authority. The reviewer gate,
  `authorize_actor`, is unchanged and still guards every one of its 45 actions — including
  `VIEW_INTELLIGENCE_REVIEW_QUEUE`, which still gates the review queue view itself.
* **Descriptive only.** Every reference is `DESCRIPTIVE_REFERENCE_ONLY`, carries its
  provenance, readiness, integrity, governance and permission states, and generalizes what
  it describes. "Prior designs often used a compact centered hierarchy" is expressible;
  "reuse this exact old layout" is not — there is no field for a file, a path, a locator or
  an asset handle, and `production_input_references()` is `[]` by contract.
* **Fail soft on absence, fail closed on leakage.** No results, blocked-only results or an
  unavailable table produce warnings and an empty context; a path-like value or a forbidden
  field in an assembled context raises instead of shipping.
"""
from __future__ import annotations

import hashlib
import json

CONTEXT_SCHEMA = "design_intelligence_context/1.0"
QUERY_PLAN_VERSION = "dip_context_query_plan/1.0"
REFERENCE_USE = "DESCRIPTIVE_REFERENCE_ONLY"

# --- bounds -------------------------------------------------------------------------
MAX_LABEL = 120
MAX_REASON = 200
MAX_SUMMARY = 300
MAX_BLOCKER_CODES = 6
MAX_WARNINGS = 12
#: per-channel result limits — small on purpose; empty context is a valid context
CHANNEL_LIMITS = {
    "HISTORICAL_DESIGN": 3,
    "DESIGN_ASSET_METADATA": 3,
    "FONT_TECHNICAL": 2,
    "BRAND_OR_PALETTE_CANDIDATE": 2,
}
#: at most this many references from one dataset lineage within a channel — one dataset
#: must not become the only voice in the room
DATASET_CAP_PER_CHANNEL = 2

CHANNEL_KINDS = {
    "HISTORICAL_DESIGN": ["HISTORICAL_DESIGN"],
    "DESIGN_ASSET_METADATA": ["DESIGN_ASSET"],
    "FONT_TECHNICAL": ["FONT"],
    "BRAND_OR_PALETTE_CANDIDATE": ["BRAND_ASSET", "BRAND_PALETTE"],
}
#: deterministic channel order — also the assembly order of the final reference list
CHANNEL_ORDER = ("HISTORICAL_DESIGN", "DESIGN_ASSET_METADATA", "FONT_TECHNICAL",
                 "BRAND_OR_PALETTE_CANDIDATE")

_TYPOGRAPHY_TRIGGERS = ("font", "type", "typograph", "serif", "sans", "script",
                        "letter", "wordmark")
_BRAND_TRIGGERS = ("brand", "logo", "palette", "lockup", "wordmark")

PROVENANCES = ("MACHINE_DERIVED", "HUMAN_VERIFIED")
FLAGS = ("UNVERIFIED", "REVIEW_REQUIRED", "RIGHTS_UNREVIEWED",
         "EVIDENCE_INTEGRITY_BLOCKED")

REFERENCE_FIELDS = (
    "corpus_item_id", "item_kind", "display_label", "dataset_lineage",
    "relevance_reason", "source_status", "provenance", "readiness_state",
    "evidence_integrity_state", "blocker_codes", "governance_state",
    "operational_permission_state", "reference_use", "flags", "blocked", "summary",
)

#: passed to the Creative Director alongside any context — the originality doctrine
#: travels WITH the data it applies to
CONTEXT_SAFEGUARDS = (
    "Historical designs are reference memory, never templates.",
    "Blocked or rights-unreviewed items are context only and cannot be reused.",
    "Machine classifications are observations, not brand truth; governance or relevance "
    "never implies operational permission.",
    "Generalize layout observations; never carry an exact source composition into a "
    "prompt seed.",
)


class DesignContextError(ValueError):
    """The assembled context would violate the contract. Refused, never shipped."""

    def __init__(self, message, code=""):
        super().__init__(message)
        self.code = code


# --- helpers -------------------------------------------------------------------------

def _is_path_like(value) -> bool:
    from apps.intelligence.semantic_document import _classify_value
    return bool(_classify_value(str(value)))


def _bounded(value, maximum, field):
    text = " ".join(str(value or "").split())[:maximum]
    if _is_path_like(text):
        raise DesignContextError(f"{field} carries a path-like value",
                                 code="PROHIBITED_VALUE")
    return text


def _safe_label(row, maximum) -> str:
    """A clean, non-path-like display label (2B-3V §5). Corpora legitimately
    store filenames in display_label / external_key; rather than fail the whole
    context (or drop the reference), fall back through external_key and finally
    a de-pathed, extension-stripped basename so an authorized reviewer still
    receives grounded context. Never raises, never leaks a locator."""
    import os
    for raw in (row.get("display_label"), row.get("external_key")):
        text = " ".join(str(raw or "").split())[:maximum]
        if text and not _is_path_like(text):
            return text
        if text:
            base = os.path.splitext(os.path.basename(text.replace("\\", "/")))[0]
            base = " ".join(base.replace("_", " ").replace("-", " ").split())[:maximum]
            if base and not _is_path_like(base):
                return base
    return f"unlabelled {row.get('item_kind', 'reference')}"


def _tokens(*values) -> str:
    seen, out = set(), []
    for value in values:
        for token in str(value or "").lower().split():
            token = token.strip(".,;:()[]\"'")
            if token and token not in seen and not _is_path_like(token):
                seen.add(token)
                out.append(token)
    return " ".join(out)[:200]


# --- query planning -------------------------------------------------------------------

def build_query_plan(brief: dict) -> list:
    """A deterministic, bounded query plan from a VALIDATED brief. Channels irrelevant to
    the brief are omitted; queries are normalized brief tokens, never LLM-generated."""
    from .design_intent import build_design_brief
    validated = build_design_brief(brief)
    plan = []
    style_text = " ".join(validated.get("preferred_styles", [])
                          + validated.get("references", [])).lower()
    plan.append({
        "channel": "HISTORICAL_DESIGN",
        "query": _tokens(validated["product_category"], validated["product_name"]),
    })
    plan.append({
        "channel": "DESIGN_ASSET_METADATA",
        "query": _tokens(validated["product_category"],
                         " ".join(validated.get("preferred_styles", []))),
    })
    if any(trigger in style_text for trigger in _TYPOGRAPHY_TRIGGERS):
        plan.append({
            "channel": "FONT_TECHNICAL",
            "query": _tokens(" ".join(validated.get("preferred_styles", []))),
        })
    if validated.get("preferred_colors") or any(
            trigger in style_text for trigger in _BRAND_TRIGGERS):
        plan.append({
            "channel": "BRAND_OR_PALETTE_CANDIDATE",
            "query": _tokens("brand palette",
                             " ".join(validated.get("preferred_colors", []))),
        })
    for entry in plan:
        entry["item_kinds"] = list(CHANNEL_KINDS[entry["channel"]])
        entry["limit"] = CHANNEL_LIMITS[entry["channel"]]
    return plan


# --- reference assembly ----------------------------------------------------------------

def _reference_from_row(row, channel, query_text) -> dict:
    integrity = row.get("evidence_integrity_state") or ""
    rights = row.get("rights_state") or ""
    readiness = row.get("readiness_state") or ""
    human_current = row.get("human_assertion_status") == "CURRENT"
    retrieval = bool((row.get("retrieval") or {}).get("allowed"))
    automatic = bool((row.get("automatic_use") or {}).get("allowed"))

    flags = []
    if integrity and integrity != "VERIFIED":
        flags.append("EVIDENCE_INTEGRITY_BLOCKED")
    if rights in ("", "UNVERIFIED", "NOT_CONFIRMED", "UNREVIEWED"):
        flags.append("RIGHTS_UNREVIEWED")
    if readiness in ("", "REVIEW_REQUIRED"):
        flags.append("REVIEW_REQUIRED")
    if not human_current:
        flags.append("UNVERIFIED")

    label = _safe_label(row, MAX_LABEL)
    kind = row.get("item_kind", "")
    summary_by_kind = {
        "HISTORICAL_DESIGN": f"historical production design '{label}' — reference "
                             "memory only; conventions may inform, layout may not be "
                             "copied",
        "DESIGN_ASSET": f"design asset candidate '{label}' — descriptive metadata only",
        "FONT": f"font family '{label}' — technical metadata only; possession is not a "
                "licence and no font is selected or attached",
        "BRAND_ASSET": f"brand candidate '{label}' — observed, unconfirmed; not brand "
                       "truth",
        "BRAND_PALETTE": f"palette candidate '{label}' — observed colors, no palette "
                         "authority",
    }
    return {
        "corpus_item_id": str(row.get("corpus_item_id", "")),
        "item_kind": kind,
        "display_label": label,
        "dataset_lineage": _bounded(row.get("dataset_identifier") or "historical",
                                    MAX_LABEL, "dataset_lineage"),
        "relevance_reason": _bounded(
            f"lexical match on '{query_text}' via {channel}", MAX_REASON,
            "relevance_reason"),
        "source_status": _bounded(row.get("identity_state") or "", MAX_LABEL,
                                  "source_status"),
        "provenance": "HUMAN_VERIFIED" if human_current else "MACHINE_DERIVED",
        "readiness_state": _bounded(readiness, MAX_LABEL, "readiness_state"),
        "evidence_integrity_state": _bounded(integrity, MAX_LABEL,
                                             "evidence_integrity_state"),
        "blocker_codes": [
            _bounded(code, MAX_LABEL, "blocker_code")
            for code in (row.get("blocker_codes") or [])[:MAX_BLOCKER_CODES]],
        "governance_state": _bounded(row.get("governance_status") or "", MAX_LABEL,
                                     "governance_state"),
        "operational_permission_state": (
            "ALL_DENIED" if not (retrieval or automatic) else "PARTIALLY_ALLOWED"),
        "reference_use": REFERENCE_USE,
        "flags": flags,
        "blocked": "EVIDENCE_INTEGRITY_BLOCKED" in flags,
        "summary": _bounded(summary_by_kind.get(kind, f"{kind} '{label}'"),
                            MAX_SUMMARY, "summary"),
    }


def _validate_reference(reference):
    unknown = set(reference) - set(REFERENCE_FIELDS)
    if unknown:
        raise DesignContextError(f"unsupported reference fields: {sorted(unknown)}",
                                 code="UNSUPPORTED_FIELD")
    if reference["reference_use"] != REFERENCE_USE:
        raise DesignContextError("reference_use must be DESCRIPTIVE_REFERENCE_ONLY",
                                 code="REFERENCE_USE_INVALID")
    if reference["provenance"] not in PROVENANCES:
        raise DesignContextError("unknown provenance", code="PROVENANCE_INVALID")
    for flag in reference["flags"]:
        if flag not in FLAGS:
            raise DesignContextError(f"unknown flag {flag!r}", code="FLAG_INVALID")


def context_hash(context) -> str:
    payload = {key: value for key, value in context.items() if key != "metadata"}
    payload["metadata"] = {
        key: value for key, value in context.get("metadata", {}).items()
        if key != "context_hash"}
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        default=str).encode()).hexdigest()


def _empty_context(authorization, warnings, plan=None):
    context = {
        "schema_version": CONTEXT_SCHEMA,
        "query_plan_version": QUERY_PLAN_VERSION,
        "references": [],
        "safeguards": list(CONTEXT_SAFEGUARDS),
        "warnings": warnings[:MAX_WARNINGS],
        "metadata": {
            "authorization": authorization,
            "queries_executed": [
                {"channel": e["channel"], "query": e["query"]} for e in (plan or [])],
            "channel_result_counts": {},
            "included": 0,
            "excluded": {},
        },
    }
    context["metadata"]["context_hash"] = context_hash(context)
    return context


# --- the adapter ------------------------------------------------------------------------

def build_design_context(user, brief: dict) -> dict:
    """Bounded, labelled, read-only DIP context for one validated brief.

    Fail-soft: unauthorized actors, empty corpora and search errors all yield an empty
    context with a warning — the creative workflow continues. Fail-closed only when an
    assembled context would leak (path-like value, forbidden field).
    """
    from apps.accounts.pipeline_capability import (
        READ_DESIGN_INTELLIGENCE_CONTEXT, authorize_pipeline_read)

    plan = build_query_plan(brief)

    # §BH58(d): a pipeline capability, not a reviewer action. The reason code carried into
    # `metadata.authorization` is this capability's own — ARIA logs that metadata into the
    # task's AgentLog on every run, which is where this decision is recorded. It is NOT
    # written to AuthorizationAudit: that table's `aa_allow_iff_role_used` constraint
    # requires an allow to name a role, and inventing one for a deliberately role-less
    # read would be the exact conflation this ruling ends.
    decision = authorize_pipeline_read(user, READ_DESIGN_INTELLIGENCE_CONTEXT)
    if not decision.allowed:
        return _empty_context(
            f"DENIED:{decision.reason_code}",
            [f"CONTEXT_UNAVAILABLE_UNAUTHORIZED:{decision.reason_code}"], plan)

    from apps.intelligence.search_contract import SearchContractError, build_search_query
    from apps.intelligence.search_service import execute_search

    references, warnings = [], []
    channel_counts, excluded = {}, {}
    seen_ids = set()
    for entry in plan:
        try:
            query = build_search_query({
                "query": entry["query"], "item_kinds": entry["item_kinds"]})
            result = execute_search(query)
        except SearchContractError:
            warnings.append(f"CHANNEL_QUERY_REFUSED:{entry['channel']}")
            channel_counts[entry["channel"]] = 0
            continue
        except Exception:                      # noqa: BLE001 — fail soft, never the workflow
            warnings.append(f"CHANNEL_UNAVAILABLE:{entry['channel']}")
            channel_counts[entry["channel"]] = 0
            continue
        rows = result.get("results", [])
        channel_counts[entry["channel"]] = len(rows)
        kept = 0
        dataset_counts = {}
        for row in rows:
            if kept >= entry["limit"]:
                excluded["over_limit"] = excluded.get("over_limit", 0) + 1
                continue
            item_id = str(row.get("corpus_item_id", ""))
            if not item_id or item_id in seen_ids:
                excluded["duplicate"] = excluded.get("duplicate", 0) + 1
                continue
            dataset = row.get("dataset_identifier") or "historical"
            if dataset_counts.get(dataset, 0) >= DATASET_CAP_PER_CHANNEL:
                excluded["dataset_cap"] = excluded.get("dataset_cap", 0) + 1
                continue
            try:
                reference = _reference_from_row(row, entry["channel"], entry["query"])
                _validate_reference(reference)
            except DesignContextError as exc:
                # a leak-guard trip on ONE row must not lose the whole context:
                # exclude that reference (never ship it) + record the bounded
                # cause, and continue assembling the rest (2B-3V §5).
                excluded["DESIGN_CONTEXT_BUILD_FAILED"] = \
                    excluded.get("DESIGN_CONTEXT_BUILD_FAILED", 0) + 1
                warnings.append(f"DESIGN_CONTEXT_REFERENCE_EXCLUDED:{exc.code or 'PROHIBITED_VALUE'}")
                continue
            references.append(reference)
            seen_ids.add(item_id)
            dataset_counts[dataset] = dataset_counts.get(dataset, 0) + 1
            kept += 1

    if not references:
        warnings.append("CONTEXT_EMPTY")

    context = {
        "schema_version": CONTEXT_SCHEMA,
        "query_plan_version": QUERY_PLAN_VERSION,
        "references": references,
        "safeguards": list(CONTEXT_SAFEGUARDS),
        "warnings": warnings[:MAX_WARNINGS],
        "metadata": {
            "authorization": "AUTHORIZED",
            "queries_executed": [
                {"channel": e["channel"], "query": e["query"]} for e in plan],
            "channel_result_counts": channel_counts,
            "included": len(references),
            "excluded": excluded,
        },
    }
    context["metadata"]["context_hash"] = context_hash(context)
    return context


def production_input_references(context) -> list:
    """Always empty, by contract — the context is text-only descriptive intelligence.
    No reference may become an image input, logo input, font file, asset file, palette
    authority, prompt attachment or IRE source."""
    return []


def to_generator_entries(context) -> list:
    """Project the context onto the generator's bounded dip_context entries. Blocked
    references stay visibly labelled; nothing but text crosses."""
    entries = []
    for reference in context.get("references", []):
        flag_text = ",".join(reference["flags"]) if reference["flags"] else "NONE"
        entries.append({
            "source": reference["provenance"],
            "blocked": reference["blocked"],
            "note": _bounded(
                f"{reference['summary']} (readiness={reference['readiness_state'] or 'n/a'};"
                f" flags={flag_text}; permissions={reference['operational_permission_state']})",
                MAX_SUMMARY + 100, "note"),
        })
    return entries
