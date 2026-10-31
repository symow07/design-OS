"""Human search-quality evaluation artifact — DIP-1C-3.

Generates a bounded, structured evaluation sheet so an authorized reviewer can rate whether
returned results were actually relevant. It is deliberately a **local artifact outside the
authority database**: there is no model, no migration, and no table.

This is **search-quality feedback only**. A rating here is not a CorpusItem assertion, not
approval, not a governance decision, not a permission, and never a DecisionEvent. Ratings
carry no authority whatsoever and must never be read as human truth about an item — only as
an opinion about whether *search* surfaced something useful.
"""
from __future__ import annotations

SHEET_SCHEMA = "intelligence_semantic_evaluation_sheet/1.0"

HIGHLY_RELEVANT = "HIGHLY_RELEVANT"
RELEVANT = "RELEVANT"
PARTIALLY_RELEVANT = "PARTIALLY_RELEVANT"
NOT_RELEVANT = "NOT_RELEVANT"
CANNOT_JUDGE = "CANNOT_JUDGE"
RATINGS = (HIGHLY_RELEVANT, RELEVANT, PARTIALLY_RELEVANT, NOT_RELEVANT, CANNOT_JUDGE)

_DISCLAIMER = (
    "SEARCH-QUALITY FEEDBACK ONLY. A rating here judges whether SEARCH surfaced something "
    "useful. It is not a CorpusItem assertion, not approval, not rights clearance, not a "
    "governance selection, and not an operational permission. It creates no DecisionEvent "
    "and grants nothing.")


def build_evaluation_sheet(evaluation: dict, *, channels=("LEXICAL", "SEMANTIC", "HYBRID"),
                           top_n=5) -> dict:
    """Turn an evaluation result into a bounded rating sheet. Read-only; writes nothing."""
    rows = []
    for query in evaluation["queries"]:
        for channel in channels:
            data = query["channels"].get(channel)
            if not data:
                continue
            for rank, (item_id, label, kind) in enumerate(
                    zip(data["top_ids"][:top_n], data["top_labels"][:top_n],
                        data["top_kinds"][:top_n]), start=1):
                rows.append({
                    "query_id": query["query_id"],
                    "query_text": query["query_text"],
                    "facet": query["facet"],
                    "channel": channel,
                    "rank": rank,
                    "corpus_item_id": item_id,
                    "display_label": label,
                    "item_kind": kind,
                    # the reviewer fills this in; nothing is pre-filled or guessed
                    "rating": "",
                    "allowed_ratings": list(RATINGS),
                    # context a rater needs to judge fairly
                    "lexical_score": (data["lexical_scores"][rank - 1]
                                      if rank <= len(data["lexical_scores"]) else None),
                    "semantic_score": (data["semantic_scores"][rank - 1]
                                       if rank <= len(data["semantic_scores"]) else None),
                    "note": _DISCLAIMER,
                })
    return {
        "schema_version": SHEET_SCHEMA,
        "disclaimer": _DISCLAIMER,
        "creates_authority": False,
        "creates_decision_events": False,
        "creates_permissions": False,
        "persisted_in_authority_database": False,
        "benchmark_schema_version": evaluation.get("benchmark_schema_version"),
        "channels": list(channels),
        "top_n": top_n,
        "row_count": len(rows),
        "rows": rows,
    }


def evaluation_sheet_csv(sheet: dict) -> str:
    """A flat CSV a reviewer can fill in offline. Bounded columns only."""
    import csv
    import io
    columns = ["query_id", "query_text", "facet", "channel", "rank", "corpus_item_id",
               "display_label", "item_kind", "lexical_score", "semantic_score", "rating"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in sheet["rows"]:
        writer.writerow(row)
    return buffer.getvalue()
