"""Semantic rescue evaluation manifest + harness — DIP-1C-5A
(`intelligence_semantic_rescue_evaluation/1.0`).

The DEVELOPMENT/HOLDOUT split is **frozen deterministically from stable query IDs and
declared stratification rules, before any full-distribution result is seen**. This is what
keeps the threshold/strategy selection honest: the config is chosen on DEVELOPMENT and
evaluated once on HOLDOUT, with no query-id-specific logic and no post-hoc split mutation.

Exact-identity controls (Q29/Q30) are held out of BOTH tuning subsets — they are the
planner's job and must never be used to tune a semantic threshold.
"""
from __future__ import annotations

from .semantic_benchmark import BENCHMARK_QUERIES

RESCUE_EVAL_SCHEMA = "intelligence_semantic_rescue_evaluation/1.0"

# exact-identity controls — reported separately, never used to tune semantic thresholds
CONTROL_IDS = ("Q29", "Q30")

# Declared stratification rule (frozen): within each stratum, even-indexed query numbers go
# to DEVELOPMENT, odd to HOLDOUT, by stable numeric query id. Deterministic from IDs alone;
# no distribution result is consulted. Strata ensure both subsets carry supported topical
# queries AND no-evidential-basis queries.
def _query_number(query_id):
    return int(query_id[1:])


def _stratum(query):
    if query.query_id in CONTROL_IDS:
        return "CONTROL"
    return "NO_BASIS" if query.expects_no_evidential_basis else "SUPPORTED"


def build_split(queries=BENCHMARK_QUERIES):
    """Deterministic DEVELOPMENT/HOLDOUT split. Controls excluded from both."""
    dev, holdout, controls = [], [], []
    # order within each stratum by numeric id so assignment is stable and declared
    for stratum in ("SUPPORTED", "NO_BASIS"):
        members = sorted((q for q in queries if _stratum(q) == stratum),
                         key=lambda q: _query_number(q.query_id))
        for position, q in enumerate(members):
            (dev if position % 2 == 0 else holdout).append(q.query_id)
    controls = sorted((q.query_id for q in queries if _stratum(q) == "CONTROL"),
                      key=_query_number)
    return {"development": dev, "holdout": holdout, "controls": controls}


def split_manifest(queries=BENCHMARK_QUERIES):
    split = build_split(queries)
    return {
        "schema_version": RESCUE_EVAL_SCHEMA,
        "benchmark_schema_version": "intelligence_semantic_benchmark/1.0",
        "stratification_rule": (
            "within each of {SUPPORTED, NO_BASIS}, queries sorted by numeric id; even "
            "position -> DEVELOPMENT, odd -> HOLDOUT. CONTROL queries excluded from both."),
        "development": split["development"],
        "holdout": split["holdout"],
        "controls": split["controls"],
        "development_count": len(split["development"]),
        "holdout_count": len(split["holdout"]),
        "control_count": len(split["controls"]),
        "total_queries": len(queries),
        "frozen_before_full_distribution": True,
    }


def _strata_counts(query_ids, queries=BENCHMARK_QUERIES):
    by_id = {q.query_id: q for q in queries}
    supported = sum(1 for qid in query_ids
                    if not by_id[qid].expects_no_evidential_basis)
    no_basis = sum(1 for qid in query_ids if by_id[qid].expects_no_evidential_basis)
    return {"supported": supported, "no_basis": no_basis}


def split_coverage(queries=BENCHMARK_QUERIES):
    split = build_split(queries)
    return {
        "development": _strata_counts(split["development"], queries),
        "holdout": _strata_counts(split["holdout"], queries),
    }


# --- reproducible rescue evaluation ---------------------------------------------
def evaluate_rescue(full_distributions, *, query_ids, strategy, thresholds=None, k=10):
    """Evaluate one (strategy, thresholds) on a set of queries, given pre-computed FULL
    semantic score distributions {query_id: {item_id: score}}. Read-only; embeds nothing.

    Deterministic and side-effect-free, so DEVELOPMENT selection and the single HOLDOUT run
    are exactly reproducible.
    """
    from .lexical_evidence import classify_lexical_evidence
    from .lexical_ranker import score_item
    from .models import (
        CorpusItem, FontFaceProfile, MachineClassification, ObservedFact,
    )
    from .rescue_ranker import assess_evidence_v1_1, plan_rescue
    from .search_planner import plan_exact_identity
    from .semantic_corpus import build_corpus_snapshot

    by_id = {q.query_id: q for q in BENCHMARK_QUERIES}
    kinds = {str(i): kind for i, kind in CorpusItem.objects.values_list("id", "item_kind")}
    labels = {}
    for iid, lab in MachineClassification.objects.values_list("corpus_item_id", "label"):
        labels.setdefault(str(iid), set()).add(lab)
    # lexical scoring must use the SAME signals production lexical search uses (external key,
    # display label, AND observed-fact / machine-classification labels) — otherwise a query
    # that matches only via a machine label (e.g. "concealer", "seamless pattern") is
    # mis-scored as having no lexical evidence, wrongly triggering semantic rescue.
    fact_labels = {}
    for iid, ft in ObservedFact.objects.values_list("corpus_item_id", "fact_type"):
        fact_labels.setdefault(str(iid), set()).add(ft)
    keys = {str(i): key for i, key in CorpusItem.objects.values_list("id", "external_key")}
    # safe labels + semantic-text group per item, from the canonical 1.2 builder
    built = build_corpus_snapshot()
    safe_labels, group_of, texts_by_item = {}, {}, {}
    for item, doc in built.documents:
        iid = str(item.pk)
        safe_labels[iid] = keys[iid]
        group_of[iid] = doc["embedding_text_hash"]
        texts_by_item[iid] = doc["embedding_text"]
    for iid, fam in FontFaceProfile.objects.values_list("corpus_item_id", "family_name"):
        safe_labels[str(iid)] = fam or safe_labels.get(str(iid), "")

    def _cat_hit(item_id, q):
        kind = kinds.get(item_id)
        if q.expected_item_kinds and kind not in q.expected_item_kinds:
            return False
        if q.expected_machine_labels:
            return bool(set(q.expected_machine_labels) & labels.get(item_id, set()))
        return bool(q.expected_item_kinds)

    def _lexical_ids_and_evidence(q, qtext):
        scored = []
        for item, doc in built.documents:
            iid = str(item.pk)
            s = score_item(qtext, external_key=keys[iid], display_label=safe_labels[iid],
                           fact_labels=fact_labels.get(iid, ()),
                           machine_labels=labels.get(iid, ()))
            if s.matched:
                scored.append((iid, s))
        scored.sort(key=lambda pair: (-pair[1].score, pair[0]))
        exact = plan_exact_identity(qtext, keys_by_id=keys, labels_by_id=safe_labels)
        ev = classify_lexical_evidence([s for _, s in scored],
                                       exact_identity=exact is not None)
        return [iid for iid, _ in scored], ev, (exact[0] if exact else None)

    rows = []
    for qid in query_ids:
        q = by_id[qid]
        dist = full_distributions[qid]
        qtext = dist["query_text"]
        semantic_ranked = [i for i, _ in sorted(
            dist["scores"].items(), key=lambda kv: (-kv[1], kv[0]))]
        top_group = group_of.get(semantic_ranked[0]) if semantic_ranked else None
        top_group_size = sum(1 for g in group_of.values() if g == top_group)
        gate = assess_evidence_v1_1(
            dist["scores"], kinds_by_id=kinds,
            expected_kinds=q.expected_item_kinds, top_group_size=top_group_size,
            thresholds=thresholds)
        lex_ids, ev, exact_id = _lexical_ids_and_evidence(q, qtext)
        plan = plan_rescue(
            strategy=strategy, lexical_classification=ev.classification,
            gate_verdict=gate.verdict, lexical_ids=lex_ids,
            semantic_ranked_ids=semantic_ranked, exact_identity_id=exact_id, k=k)
        ordered = list(plan.ordered_ids)
        hits = [_cat_hit(i, q) for i in ordered]

        def _p(n):
            top = hits[:n]
            return round(sum(top) / len(top), 3) if top else 0.0
        first_rank = next((r + 1 for r, h in enumerate(hits) if h), None)
        rows.append({
            "query_id": qid, "query_text": qtext,
            "expects_no_evidential_basis": q.expects_no_evidential_basis,
            "is_control": qid in CONTROL_IDS,
            "lexical_classification": ev.classification,
            "gate_verdict": gate.verdict,
            "gate_top": gate.top_score, "gate_margin": gate.top_to_median_margin,
            "gate_percentile": gate.top_percentile,
            "channel_used": plan.channel_used, "abstained": plan.abstained,
            "returned": len(ordered),
            "precision_at_1": _p(1), "precision_at_5": _p(5), "precision_at_10": _p(10),
            "reciprocal_rank": round(1.0 / first_rank, 3) if first_rank else 0.0,
            "hit_at_1": bool(hits[:1] and hits[0]),
            "hit_at_5": any(hits[:5]), "hit_at_10": any(hits[:10]),
            "exact_identity_first": (
                exact_id is not None and ordered[:1] == [exact_id]),
            "top_ids": ordered[:5],
        })
    return {"strategy": strategy,
            "thresholds": thresholds,
            "rows": rows,
            "summary": _rescue_summary(rows)}


def _rescue_summary(rows):
    supported = [r for r in rows if not r["expects_no_evidential_basis"]
                 and not r["is_control"]]
    no_basis = [r for r in rows if r["expects_no_evidential_basis"]]
    controls = [r for r in rows if r["is_control"]]

    def _mean(items, field):
        return round(sum(r[field] for r in items) / len(items), 3) if items else 0.0
    # a no-basis query is correctly abstained if the rescue used no semantic channel
    nb_correct = sum(1 for r in no_basis
                     if r["channel_used"] in ("LEXICAL", "EMPTY"))
    # a supported query falsely abstains if it produced an empty result
    sup_false_abstain = sum(1 for r in supported if r["channel_used"] == "EMPTY")
    return {
        "supported_count": len(supported),
        "no_basis_count": len(no_basis),
        "control_count": len(controls),
        "supported_mean_precision_at_1": _mean(supported, "precision_at_1"),
        "supported_mean_reciprocal_rank": _mean(supported, "reciprocal_rank"),
        "supported_hit_at_1": sum(1 for r in supported if r["hit_at_1"]),
        "no_basis_abstention_accuracy": (
            round(nb_correct / len(no_basis), 3) if no_basis else 0.0),
        "no_basis_false_positive_rate": (
            round((len(no_basis) - nb_correct) / len(no_basis), 3) if no_basis else 0.0),
        "supported_false_abstention_rate": (
            round(sup_false_abstain / len(supported), 3) if supported else 0.0),
        "controls_first": sum(1 for r in controls if r["exact_identity_first"]),
        "control_total": len(controls),
    }
