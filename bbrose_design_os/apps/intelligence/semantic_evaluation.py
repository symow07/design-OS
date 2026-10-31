"""Benchmark execution and search-quality evaluation — DIP-1C-3.

Runs the `intelligence_semantic_benchmark/1.0` queries through the lexical, semantic and
hybrid channels and reports what each returned. It is **measurement only**: it writes
nothing, approves nothing, and creates no authority. It never modifies the corpus in
response to an outcome.

Precision here is **category-level** — the share of returned items whose kind (or recorded
machine label) matches what the query category expects. There is no human relevance ground
truth for this corpus, so this is a coverage signal, not an accuracy claim, and the sample
is far too small for statistical significance.
"""
from __future__ import annotations

from .models import CorpusItem, DesignAssetProfile, FontFaceProfile, MachineClassification
from .search_contract import RANK_HYBRID, RANK_LEXICAL, RANK_SEMANTIC, build_search_query
from .search_service import execute_search
from .semantic_benchmark import BENCHMARK_QUERIES, BENCHMARK_SCHEMA

EVALUATION_SCHEMA = "intelligence_semantic_evaluation/1.1"
DEFAULT_K = 10
# the published pilot's schema — used to derive safe labels and semantic-text groups
SEMANTIC_DOC_SCHEMA_FOR_EVAL = "intelligence_semantic_document/1.2"

# A "meaningful semantic channel" is a field carrying descriptive or observational content
# a reviewer could plausibly search on. Identity and schema plumbing — external_key,
# item_kind, dataset_identifier, schema_version — do NOT count: they are how we name a
# thing, not what it is. This definition is fixed here so the metric cannot be quietly
# widened to make coverage look better.
MEANINGFUL_CHANNELS = (
    "display_label", "machine_product_family_labels", "style_labels",
    "observed_script_coverage", "observed_fact_values",
    "machine_classification_labels", "human_assertion_labels",
)


def _meaningful_channel_count(document):
    return sum(1 for field in MEANINGFUL_CHANNELS if document.get(field))


def document_quality_report():
    """Diagnostic only. Never invents descriptions and never substitutes a filename or
    path for missing semantics."""
    import statistics
    from .semantic_document import build_semantic_document, semantic_text
    from .semantic_index import _indexable_items, SemanticDocumentError

    docs, omissions, excluded = [], {}, []
    for item in _indexable_items():
        try:
            document, diagnostics = build_semantic_document(item, with_diagnostics=True)
        except SemanticDocumentError as exc:
            excluded.append({"external_key": item.external_key,
                             "reason_code": getattr(exc, "code", "")})
            continue
        docs.append((item, document))
        for diagnostic in diagnostics:
            key = f"{diagnostic['field']}:{diagnostic['reason_code']}"
            omissions[key] = omissions.get(key, 0) + 1

    lengths = [len(semantic_text(d)) for _, d in docs]
    fonts = [d for _, d in docs if d["item_kind"] == "FONT"]
    channels = [_meaningful_channel_count(d) for _, d in docs]
    return {
        "total_indexable_documents": len(docs),
        "excluded_documents": len(excluded),
        "exclusions": excluded,
        "with_safe_display_label": sum(1 for _, d in docs if d.get("display_label")),
        "without_display_label": sum(1 for _, d in docs if not d.get("display_label")),
        "with_product_family_metadata": sum(
            1 for _, d in docs if d.get("machine_product_family_labels")),
        "with_style_metadata": sum(1 for _, d in docs if d.get("style_labels")),
        "font_documents": len(fonts),
        "font_documents_with_script_coverage": sum(
            1 for d in fonts if d.get("observed_script_coverage")),
        "with_verified_human_labels": sum(
            1 for _, d in docs if d.get("human_assertion_labels")),
        "identity_or_enum_only": sum(1 for count in channels if count == 0),
        "two_or_more_meaningful_channels": sum(1 for count in channels if count >= 2),
        "meaningful_channel_distribution": {
            str(n): channels.count(n) for n in sorted(set(channels))},
        "omitted_optional_fields_by_reason": dict(sorted(omissions.items())),
        "mean_document_length": round(statistics.mean(lengths), 1) if lengths else 0,
        "median_document_length": round(statistics.median(lengths), 1) if lengths else 0,
        "max_document_length": max(lengths) if lengths else 0,
        "meaningful_channel_definition": list(MEANINGFUL_CHANNELS),
    }


def _machine_labels_by_item():
    labels = {}
    for item_id, label in MachineClassification.objects.values_list(
            "corpus_item_id", "label"):
        labels.setdefault(str(item_id), set()).add(label)
    return labels


def bind_control_queries(queries=BENCHMARK_QUERIES):
    """Bind the exact-identity control queries to REAL live corpus evidence, rather than
    hard-coding an ID that might not exist."""
    bound = []
    asset = DesignAssetProfile.objects.select_related("corpus_item").first()
    font = FontFaceProfile.objects.select_related("corpus_item").first()
    for q in queries:
        if q.query_id == "Q29" and asset is not None:
            bound.append((q, asset.corpus_item.external_key,
                          str(asset.corpus_item_id)))
        elif q.query_id == "Q30" and font is not None:
            bound.append((q, font.family_name, str(font.corpus_item_id)))
        else:
            bound.append((q, q.query_text, None))
    return bound


def _category_hit(item_id, kinds_by_item, labels_by_item, query):
    """Is this result in the category the query asked for?

    When a query names expected machine labels, the label must match — matching the item
    KIND alone is not enough. Kind-only matching inflates precision to ~1.0 on every broad
    query (e.g. "lip colour product" returns ten historical designs and all ten score as
    hits merely for being historical designs, though only one carries a lip-colour label),
    which would make any lexical-vs-semantic comparison meaningless.
    """
    kind = kinds_by_item.get(item_id)
    if query.expected_item_kinds and kind not in query.expected_item_kinds:
        return False
    if query.expected_machine_labels:
        return bool(set(query.expected_machine_labels) & labels_by_item.get(item_id, set()))
    return bool(query.expected_item_kinds)


def run_channel(query, query_text, *, ranking, k=DEFAULT_K, query_vector=None,
                keys_by_id=None, labels_by_id=None):
    """Run one benchmark query through one channel, then apply the exact-identity planner.

    Read-only. The planner (`intelligence_search_planner/1.0`) pins an exact stable-key or
    safe-label match to rank 1 with reason EXACT_IDENTITY_MATCH — an identity operation, not
    an inflated semantic score. Requesting more than k so the pin can promote a true match
    that ranking alone left below the cut.
    """
    from .search_planner import apply_identity_pin, plan_exact_identity
    search_query = build_search_query({
        "query": query_text,
        "ranking": ranking,
        "scope": query.scope,
        "limit": 100,       # rank widely, pin, then the caller truncates to k
        "allow_lexical_fallback": ranking != RANK_SEMANTIC,
    })
    result = execute_search(search_query, query_vector=query_vector)
    if keys_by_id is not None:
        plan = plan_exact_identity(query_text, keys_by_id=keys_by_id,
                                   labels_by_id=labels_by_id or {})
        if plan is not None:
            result["results"] = apply_identity_pin(result["results"], plan[0])
    return result


def evaluate(*, k=DEFAULT_K, channels=(RANK_LEXICAL,), vector_provider=None):
    """Run the whole benchmark across the given channels.

    `vector_provider(query_text) -> vector | None` supplies a pre-embedded query vector for
    the semantic/hybrid channels. Nothing here calls a provider itself.
    """
    kinds_by_item = {str(i): k_ for i, k_ in
                     CorpusItem.objects.values_list("id", "item_kind")}
    labels_by_item = _machine_labels_by_item()
    keys_by_id = {str(i): key for i, key in
                  CorpusItem.objects.values_list("id", "external_key")}
    # safe display label per item, from the canonical 1.2 builder (never a filename)
    from .semantic_builders import build_semantic_corpus
    built = build_semantic_corpus(document_schema_version=SEMANTIC_DOC_SCHEMA_FOR_EVAL)
    labels_by_id, group_by_id = {}, {}
    for entry_b in built.entries:
        iid = str(entry_b.corpus_item.pk)
        labels_by_id[iid] = entry_b.document.get("metadata", {}).get("external_key", "")
        # semantic-text group = items sharing an embedding-text hash (identical vectors)
        group_by_id[iid] = entry_b.embedding_text_hash
    # font family names are safe exact-label targets for the Q30 control
    for iid, fam in FontFaceProfile.objects.values_list("corpus_item_id", "family_name"):
        labels_by_id[str(iid)] = fam or labels_by_id.get(str(iid), "")

    def _cat_hit(item_id, query):
        return _category_hit(item_id, kinds_by_item, labels_by_item, query)

    rows = []
    for query, query_text, expected_id in bind_control_queries():
        entry = {
            "query_id": query.query_id,
            "query_text": query_text,
            "facet": query.facet,
            "scope": query.scope,
            "expects_no_evidential_basis": query.expects_no_evidential_basis,
            "expected_item_kinds": list(query.expected_item_kinds),
            "expected_machine_labels": list(query.expected_machine_labels),
            "control_expected_item_id": expected_id,
            "channels": {},
        }
        for ranking in channels:
            vector = None
            if ranking in (RANK_SEMANTIC, RANK_HYBRID) and vector_provider is not None:
                vector = vector_provider(query_text)
            result = run_channel(query, query_text, ranking=ranking, k=k,
                                 query_vector=vector, keys_by_id=keys_by_id,
                                 labels_by_id=labels_by_id)
            full = result["results"]
            results = full[:k]                    # metrics at k after planner pinning
            hit_flags = [_cat_hit(r["corpus_item_id"], query) for r in results]

            def _p_at(n):
                top = hit_flags[:n]
                return round(sum(top) / len(top), 3) if top else 0.0

            # semantic-group precision: a correct-category hit credits its whole
            # embedding-text group (identical vectors can't be told apart within a group)
            hit_groups = {group_by_id.get(r["corpus_item_id"])
                          for r, ok in zip(results, hit_flags) if ok}
            hit_groups.discard(None)
            returned_groups = {group_by_id.get(r["corpus_item_id"]) for r in results}
            returned_groups.discard(None)

            entry["channels"][ranking] = {
                "result_label": result.get("result_label"),
                "ranking_engaged": result.get("ranking_engaged"),
                "ranking_is_semantic": result.get("ranking_is_semantic"),
                "total_results": result["total_results"],
                "returned": len(results),
                "precision_at_1": _p_at(1),
                "precision_at_5": _p_at(5),
                "precision_at_10": _p_at(10),
                "category_hits_at_k": sum(hit_flags),
                "category_precision_at_k": _p_at(k),
                "semantic_group_precision": (
                    round(len(hit_groups) / len(returned_groups), 3)
                    if returned_groups else 0.0),
                "distinct_groups_returned": len(returned_groups),
                "empty": not results,
                "top_ids": [r["corpus_item_id"] for r in results[:10]],
                "top_labels": [r["display_label"] for r in results[:10]],
                "top_kinds": [r["item_kind"] for r in results[:10]],
                "lexical_scores": [r["lexical_score"] for r in results[:10]],
                "semantic_scores": [r["semantic_score"] for r in results[:10]],
                "match_reasons": [r["match_reasons"] for r in results[:3]],
                "blocker_codes": [r["blocker_codes"] for r in results[:3]],
                "campaign_membership": [r["campaign_membership"] for r in results[:3]],
                # these must stay false/zero on every channel
                "retrieval_allowed_count": sum(
                    1 for r in results if r["retrieval"]["allowed"]),
                "automatic_use_allowed_count": sum(
                    1 for r in results if r["automatic_use"]["allowed"]),
                # control: exact-identity pinned first via the PLANNER (reason, not score)
                "control_rank_1_correct": (
                    bool(results) and expected_id is not None
                    and results[0]["corpus_item_id"] == expected_id),
                "control_reason_is_exact_identity": (
                    bool(results) and expected_id is not None
                    and "EXACT_IDENTITY_MATCH" in results[0].get("match_reasons", [])),
            }
        rows.append(entry)

    return {
        "schema_version": EVALUATION_SCHEMA,
        "benchmark_schema_version": BENCHMARK_SCHEMA,
        "k": k,
        "channels": list(channels),
        "relevance_labelling": "CATEGORY_LEVEL_ONLY_NO_HUMAN_GROUND_TRUTH",
        "statistical_note": (
            "A ~30-query benchmark cannot support a significance claim; these are "
            "directional coverage observations only."),
        "queries": rows,
        "summary": _summarize(rows, channels),
    }


def _summarize(rows, channels):
    summary = {}
    for ranking in channels:
        entries = [r["channels"][ranking] for r in rows if ranking in r["channels"]]
        scored = [e for e in entries if not e["empty"]]
        def _mean(field):
            return round(sum(e[field] for e in scored) / len(scored), 3) if scored else 0.0
        summary[ranking] = {
            "queries": len(entries),
            "empty_results": sum(1 for e in entries if e["empty"]),
            "empty_rate": round(
                sum(1 for e in entries if e["empty"]) / len(entries), 3) if entries else 0.0,
            "mean_precision_at_1": _mean("precision_at_1"),
            "mean_precision_at_5": _mean("precision_at_5"),
            "mean_precision_at_10": _mean("precision_at_10"),
            "mean_category_precision_at_k": _mean("category_precision_at_k"),
            "mean_semantic_group_precision": _mean("semantic_group_precision"),
            "controls_ranked_first": sum(
                1 for e in entries if e["control_rank_1_correct"]),
            "controls_via_exact_identity_reason": sum(
                1 for e in entries if e["control_reason_is_exact_identity"]),
            "retrieval_allowed_total": sum(e["retrieval_allowed_count"] for e in entries),
            "automatic_use_allowed_total": sum(
                e["automatic_use_allowed_count"] for e in entries),
        }
    return summary
