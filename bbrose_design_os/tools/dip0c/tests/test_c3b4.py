"""DIP-0C3b4 — scope taxonomy, conflicts, atomic resolution, queues."""
from __future__ import annotations

import json

import pytest

from tools.dip0c import authz
from tools.dip0c import canonical_master as CM
from tools.dip0c import canonical_read as CR
from tools.dip0c import canonical_scope as S
from tools.dip0c import compound as CP
from tools.dip0c import config as C
from tools.dip0c import conflict_resolution as RES
from tools.dip0c import ledger as L
from tools.dip0c import review_c3b4 as RV
from tools.dip0c import run_c3b4
from tools.dip0c import taxonomy as TX

T = "2026-07-14T09:00:00+00:00"
T2 = "2026-07-14T12:00:00+00:00"
NOW = "2026-07-14T13:00:00+00:00"
TECH, LEGAL = "alice", "bob"


def _atts(tech=TECH, legal=LEGAL):
    return [CM.attestation(CM.ATT_TECHNICAL, actor_id=tech,
                           actor_role=authz.BRAND_ADMIN, attested_at=T),
            CM.attestation(CM.ATT_LEGAL, actor_id=legal,
                           actor_role=authz.LEGAL_REVIEWER, attested_at=T)]


def _cl(tech=TECH, legal=LEGAL):
    cl = CM.blank_checklist()
    for k in cl:
        by = tech if k in CM.TECHNICAL_ITEMS else legal
        cl[k] = {"result": True, "confirmed_by": by, "confirmed_at": T, "notes": ""}
    return cl


def _sc(**kw):
    return S.scope("BBROSE", **kw)


def _activate(asset, scope, at=T):
    return L.event(asset, event_type=L.CANONICAL_MASTER_APPROVED, actor_id=TECH,
                   actor_role=authz.BRAND_ADMIN, occurred_at=at,
                   decision_reason="r",
                   canonical=L.canonical_block(C.CANONICAL_BRAND_MASTER, scope=scope,
                                               checklist=_cl(), attestations=_atts()))


# === the taxonomy: axis-specific, and it never guesses ========================
@pytest.mark.parametrize("axis,a,b,want", [
    ("markets", "EU", "FR", TX.OVERLAPPING),
    ("markets", "FR", "DE", TX.DISJOINT),
    ("markets", "EU", "US", TX.DISJOINT),
    ("markets", "EU", "ATLANTIS", TX.UNKNOWN),
    ("markets", "EU", "EUROPE", TX.IDENTICAL),
    ("markets", "EEC", "EU", TX.IDENTICAL),
    ("products", "LIP_GLOSS", "MASCARA", TX.DISJOINT),
    ("products", "MAKEUP", "LIP_GLOSS", TX.OVERLAPPING),
    ("products", "COSMETICS", "MAKEUP", TX.OVERLAPPING),
    ("products", "WIDGET", "LIP_GLOSS", TX.UNKNOWN),
    ("products", "PACKAGING", "LIP_GLOSS", TX.UNKNOWN),
    ("lockups", "PRIMARY", "PRIMARY_HORIZONTAL", TX.OVERLAPPING),
    ("lockups", "PRIMARY_HORIZONTAL", "PRIMARY_VERTICAL", TX.DISJOINT),
    ("lockups", "PRIMARY", "STACKED", TX.UNKNOWN),
])
def test_axis_specific_token_relations(axis, a, b, want):
    rel, _ = TX.relate_tokens(axis, a, b)
    assert rel == want


def test_disjointness_is_never_inferred_from_a_missing_edge():
    """A GENERAL token might contain the thing it is compared to."""
    rel, why = TX.relate_tokens("products", "PACKAGING", "MASCARA")
    assert rel == TX.UNKNOWN
    assert "GENERAL" in why


def test_an_unregistered_token_fails_closed():
    assert S.collides(_sc(markets=["EU"]), _sc(markets=["NOWHERE"]))
    rel = S.relate(_sc(markets=["EU"]), _sc(markets=["NOWHERE"]))
    assert rel["relation"] == S.UNKNOWN
    assert rel["proven"] is False


def test_nothing_is_inferred_from_spelling():
    """LIPGLOSS resolves only because an alias says so — not because it looks alike."""
    assert TX.resolve("products", "LIPGLOSS")["token"] == "LIP_GLOSS"
    assert TX.resolve("products", "LIP_GLOS")["known"] is False   # a typo stays UNKNOWN


# === the quad-state ==========================================================
def test_identical_scopes_conflict():
    a, b = _activate("a.ai", _sc()), _activate("b.ai", _sc(), at=T2)
    c = CR.conflicts([a, b])
    assert len(c) == 1
    assert c[0]["relation"] == S.IDENTICAL
    assert c[0]["proven"] is True


def test_disjoint_scopes_do_not_conflict():
    a = _activate("a.ai", _sc(markets=["FR"]))
    b = _activate("b.ai", _sc(markets=["DE"]), at=T2)
    assert CR.conflicts([a, b]) == []


def test_uncertain_market_overlap_requires_review():
    a = _activate("a.ai", _sc(markets=["EU"]))
    b = _activate("b.ai", _sc(markets=["ATLANTIS"]), at=T2)
    c = CR.conflicts([a, b])
    assert len(c) == 1
    assert c[0]["uncertain"] is True
    q = RV.build([a, b], now=NOW)
    assert q["queues"]["D"]["count"] >= 1        # uncertainty is queued, not ignored


def test_incomplete_data_never_silently_becomes_all():
    inc = _sc(incomplete_axes=("markets",))
    assert inc["markets"]["mode"] == S.MODE_INCOMPLETE
    assert S.relate(inc, _sc(markets=["FR"]))["relation"] == S.UNKNOWN


def test_omission_means_all_and_all_overlaps_everything():
    assert _sc()["markets"]["mode"] == S.MODE_ALL
    assert S.relate(_sc(), _sc(markets=["FR"]))["relation"] == S.OVERLAPPING


def test_touching_periods_are_disjoint_half_open():
    a = _sc(valid_from="2026-01-01T00:00:00+00:00",
            valid_until="2027-01-01T00:00:00+00:00")
    b = _sc(valid_from="2027-01-01T00:00:00+00:00")
    assert S.relate(a, b)["relation"] == S.DISJOINT


def test_a_malformed_period_fails_closed():
    assert S.relate(_sc(valid_from="not-a-date"), _sc())["relation"] == S.UNKNOWN
    # a naive timestamp is not a UTC instant
    assert S.relate(_sc(valid_from="2026-01-01T00:00:00"),
                    _sc())["relation"] == S.UNKNOWN


def test_a_proven_disjoint_axis_beats_uncertainty_elsewhere():
    a = _sc(markets=["FR"], products=["WIDGET"])
    b = _sc(markets=["DE"], products=["LIP_GLOSS"])
    assert S.relate(a, b)["relation"] == S.DISJOINT      # markets settle it


def test_the_legacy_boolean_overlap_path_is_gone():
    """One system, one notion of overlap. A second, boolean one would eventually
    disagree with the quad-state — and the disagreement would let a master through."""
    import pathlib
    assert not hasattr(CM, "scopes_overlap")
    for p in pathlib.Path("tools/dip0c").glob("*.py"):
        src = p.read_text()
        assert "def scopes_overlap" not in src, f"{p.name} still defines it"
        assert "scopes_overlap(" not in src, f"{p.name} still calls it"
    # ...and every canonical workflow routes through the ONE implementation
    assert CM.collides(_sc(markets=["EU"]), _sc(markets=["ATLANTIS"])) is True
    assert CM.collides(_sc(markets=["FR"]), _sc(markets=["DE"])) is False


# === two active overlapping masters ==========================================
def test_the_read_model_never_returns_two_active_overlapping_masters():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    fr = _activate("fr.ai", _sc(markets=["FR"]), at=T2)
    q = CR.canonical_for([eu, fr], _sc(markets=["FR"]))
    assert q["state"] == CR.CANONICAL_CONFLICT
    assert q["asset"] is None
    assert q["usable"] is False
    assert sorted(q["conflicting_assets"]) == ["eu.ai", "fr.ai"]


def test_the_projection_never_lists_two_overlapping_actives():
    """The acceptance criterion is about the READ MODEL, not just one query. Two
    conflicted masters must not appear side by side in `active` — they move to
    `conflicted`, which is what a caller must not mistake for usable."""
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    fr = _activate("fr.ai", _sc(markets=["FR"]), at=T2)
    us = _activate("us.ai", _sc(markets=["US"]), at=T2)
    proj = CR.project([eu, fr, us], now=NOW)

    assert [m["asset"] for m in proj["active"]] == ["us.ai"]
    assert sorted(m["asset"] for m in proj["conflicted"]) == ["eu.ai", "fr.ai"]
    assert proj["conflict_free"] is False

    # no two masters listed as active may overlap — the property, stated directly
    act = [m for m in proj["active"] if m["scope"]]
    for i, a in enumerate(act):
        for b in act[i + 1:]:
            assert S.relate(a["scope"], b["scope"])["relation"] == S.DISJOINT


def test_no_winner_is_chosen_by_timestamp_filename_or_quality():
    eu = _activate("aaa_old.ai", _sc(markets=["EU"]))
    fr = _activate("zzz_new.ai", _sc(markets=["FR"]), at=T2)
    q = CR.canonical_for([eu, fr], _sc(markets=["FR"]))
    assert q["asset"] is None          # the NEWER one did not silently win


def test_a_conflict_is_scope_local():
    """A fight over France must not invalidate a master approved only for the US."""
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    us = _activate("us.ai", _sc(markets=["US"]), at=T2)
    fr = _activate("fr.ai", _sc(markets=["FR"]), at=T2)
    ev = [eu, us, fr]
    assert CR.canonical_for(ev, _sc(markets=["US"]))["usable"] is True
    assert CR.canonical_for(ev, _sc(markets=["US"]))["asset"] == "us.ai"
    assert CR.canonical_for(ev, _sc(markets=["FR"]))["state"] == CR.CANONICAL_CONFLICT


def test_the_conflict_reports_affected_and_uncertain_scope():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    fr = _activate("fr.ai", _sc(markets=["FR"]), at=T2)
    c = CR.conflicts([eu, fr])[0]
    assert c["affected_scope"]["brand"] == "BBROSE"
    assert c["proven"] is True
    assert c["resolution_is_human_only"] is True
    assert set(c["permitted_resolutions"]) == set(RES.ACTIONS)


# === resolution ==============================================================
def test_a_replacement_without_incumbent_resolution_is_rejected():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    rogue = _activate("new.ai", _sc(markets=["EU"]), at=T2)   # a bare second approval
    assert len(CR.conflicts([eu, rogue])) == 1                # it does NOT resolve it


def test_resolution_is_atomic_and_leaves_exactly_one_active():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    us = _activate("us.ai", _sc(markets=["US"]))
    _, rec = RES.resolve(
        RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
        existing_events=[eu, us], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
        occurred_at=T2, reason="new master", new_asset="eu2.ai",
        new_scope=_sc(markets=["EU"]), attestations=_atts(), checklist=_cl(),
        dry_run=True)
    post = [eu, us] + rec["constituents"]
    assert CR.conflicts(post) == []
    states = {m["asset"]: m["lifecycle"] for m in CR.masters(post)}
    assert states == {"eu.ai": CR.SUPERSEDED, "eu2.ai": CR.ACTIVE,
                      "us.ai": CR.ACTIVE}
    assert CR.canonical_for(post, _sc(markets=["EU"]))["asset"] == "eu2.ai"


def test_the_constituents_are_embedded_not_written_separately():
    """One file, one write. There is no interval with two active masters."""
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    _, rec = RES.resolve(
        RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
        existing_events=[eu], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
        occurred_at=T2, reason="r", new_asset="eu2.ai",
        new_scope=_sc(markets=["EU"]), attestations=_atts(), checklist=_cl(),
        dry_run=True)
    assert len(rec["constituents"]) == 2
    assert rec["constituent_ids"] == [e["event_id"] for e in rec["constituents"]]
    for e in rec["constituents"]:
        assert rec["constituent_hashes"][e["event_id"]] == L.content_hash(e)


def test_a_resolution_actually_commits_and_round_trips(tmp_path, monkeypatch):
    """The atomic writer, ACTUALLY RUN. Every other resolution test is dry_run, so
    without this one `os.replace`, the fsyncs, `load_all` and `expand` are never
    executed — and an atomic writer that has never written is not evidence of
    anything."""
    monkeypatch.setattr(CP, "COMPOUND_DIR", tmp_path / "compound")
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    us = _activate("us.ai", _sc(markets=["US"]))
    path, rec = RES.resolve(                       # NOT dry_run
        RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
        existing_events=[eu, us], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
        occurred_at=T2, reason="a new EU master", new_asset="eu2.ai",
        new_scope=_sc(markets=["EU"]), attestations=_atts(), checklist=_cl())

    assert path.exists()
    assert path.name == f"{rec['compound_event_id']}.json"
    assert not list((tmp_path / "compound").glob("*.tmp"))     # no debris

    loaded = CP.load_all()
    assert len(loaded) == 1
    assert loaded[0]["compound_content_hash"] == CP.content_hash(loaded[0])

    # the constituents read back, and project to exactly one active master per scope
    states = {m["asset"]: m["lifecycle"] for m in CR.masters([eu, us] + CP.expand())}
    assert states == {"eu.ai": CR.SUPERSEDED, "eu2.ai": CR.ACTIVE, "us.ai": CR.ACTIVE}
    assert CR.conflicts([eu, us] + CP.expand()) == []
    assert CP.validate_committed()["valid"]

    # append-only: the same resolution may not be written twice
    with pytest.raises(CP.CompoundError, match="APPEND-ONLY"):
        CP.commit(rec, existing_events=[eu, us])


def test_a_tampered_compound_file_is_detected(tmp_path, monkeypatch):
    monkeypatch.setattr(CP, "COMPOUND_DIR", tmp_path / "compound")
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    path, _ = RES.resolve(
        RES.DEPRECATE_INCUMBENT, incumbent_event_id=eu["event_id"],
        existing_events=[eu], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
        occurred_at=T2, reason="retired")
    assert CP.validate_committed()["valid"]

    doc = json.loads(path.read_text())
    doc["decision_reason"] = "something else entirely"
    path.write_text(json.dumps(doc, indent=2))
    report = CP.validate_committed()
    assert not report["valid"]
    assert any("content hash mismatch" in p for p in report["problems"])


def test_a_failed_compound_operation_appends_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(CP, "COMPOUND_DIR", tmp_path / "compound")
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    before = sorted(p.name for p in tmp_path.rglob("*"))
    with pytest.raises((CP.CompoundError, L.LedgerError)):
        RES.resolve(RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
                    existing_events=[eu], actor_id=TECH,
                    actor_role=authz.BRAND_ADMIN, occurred_at=T2, reason="r",
                    new_asset="x.ai", new_scope=_sc(markets=["EU"]),
                    attestations=[_atts()[0]], checklist=_cl())
    assert sorted(p.name for p in tmp_path.rglob("*")) == before


def test_a_post_state_with_overlapping_actives_is_refused_before_writing():
    """The last line of defence: even a well-formed compound is refused if the
    projected result would hold two active masters."""
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    fr = _activate("fr.ai", _sc(markets=["FR"]), at=T2)
    bogus = _activate("new.ai", _sc(markets=["EU"]), at=T2)
    rec = CP.build("DEPRECATE_INCUMBENT", asset="x.ai", actor_id=TECH,
                   actor_role=authz.BRAND_ADMIN, occurred_at=T2, reason="r",
                   constituents=[bogus])
    problems = CP.validate(rec, existing_events=[eu, fr])
    assert any("two active canonical masters" in p for p in problems)


def test_deprecation_preserves_the_historical_events():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    _, rec = RES.resolve(RES.DEPRECATE_INCUMBENT, incumbent_event_id=eu["event_id"],
                         existing_events=[eu], actor_id=TECH,
                         actor_role=authz.BRAND_ADMIN, occurred_at=T2,
                         reason="retired", dry_run=True)
    post = [eu] + rec["constituents"]
    m = CR.masters(post)[0]
    assert m["lifecycle"] == CR.DEPRECATED
    assert eu["event_id"] in m["history"]        # the activation is NOT erased
    assert eu in post                            # ...nor overwritten


def test_supersession_links_old_and_new_explicitly():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    _, rec = RES.resolve(
        RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
        existing_events=[eu], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
        occurred_at=T2, reason="r", new_asset="eu2.ai",
        new_scope=_sc(markets=["EU"]), attestations=_atts(), checklist=_cl(),
        dry_run=True)
    ms = CR.masters([eu] + rec["constituents"])
    old = next(m for m in ms if m["asset"] == "eu.ai")
    assert old["lifecycle"] == CR.SUPERSEDED
    assert old["superseded_by"]["asset"] == "eu2.ai"
    chains = CR._chains(ms)
    assert chains[0]["from_asset"] == "eu.ai" and chains[0]["to_asset"] == "eu2.ai"


def test_deprecated_superseded_rejected_and_quarantined_are_distinct():
    assert len({CR.DEPRECATED, CR.SUPERSEDED, CR.REJECTED, CR.QUARANTINED}) == 4
    assert set(CR.LIFECYCLE) == {CR.ACTIVE, CR.DEPRECATED, CR.SUPERSEDED,
                                 CR.REJECTED, CR.QUARANTINED}


# === narrowing and widening ==================================================
def test_narrowing_reduces_scope_only():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    _, rec = RES.resolve(RES.NARROW_INCUMBENT_SCOPE,
                         incumbent_event_id=eu["event_id"], existing_events=[eu],
                         actor_id=TECH, actor_role=authz.BRAND_ADMIN,
                         occurred_at=T2, reason="France only",
                         narrowed_scope=_sc(markets=["FR"]), dry_run=True)
    assert rec["constituents"][0]["event_type"] == L.SCOPE_REDUCED
    m = CR.masters([eu] + rec["constituents"])[0]
    assert m["scope"]["markets"]["tokens"] == ["FR"]


def test_narrowing_uses_containment_not_set_difference():
    """EU -> FR removes nothing from a SET point of view, yet France is inside the
    EU. Only the taxonomy can tell a narrowing from a widening."""
    d = S.narrowing_delta(_sc(markets=["EU"]), _sc(markets=["FR"]))
    assert d["is_narrowing"] and not d["is_widening"]
    w = S.narrowing_delta(_sc(markets=["FR"]), _sc(markets=["EU"]))
    assert w["is_widening"] and not w["is_narrowing"]


def test_widening_requires_a_new_full_approval():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    with pytest.raises(RES.ResolutionError, match="WIDENS"):
        RES.resolve(RES.NARROW_INCUMBENT_SCOPE, incumbent_event_id=eu["event_id"],
                    existing_events=[eu], actor_id=TECH,
                    actor_role=authz.BRAND_ADMIN, occurred_at=T2, reason="r",
                    narrowed_scope=_sc(markets=["EU", "US"]))


def test_a_scope_change_that_cannot_be_proven_to_reduce_is_refused():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    with pytest.raises(RES.ResolutionError):
        RES.resolve(RES.NARROW_INCUMBENT_SCOPE, incumbent_event_id=eu["event_id"],
                    existing_events=[eu], actor_id=TECH,
                    actor_role=authz.BRAND_ADMIN, occurred_at=T2, reason="r",
                    narrowed_scope=_sc(markets=["ATLANTIS"]))


# === dual control survives the conflict path ================================
def test_a_variant_cannot_silently_become_the_canonical_master():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    with pytest.raises(RES.ResolutionError, match="dual control"):
        RES.resolve(RES.RECLASSIFY_AS_VARIANT, incumbent_event_id=eu["event_id"],
                    existing_events=[eu], actor_id=TECH,
                    actor_role=authz.BRAND_ADMIN, occurred_at=T2, reason="r",
                    variant_state=C.CANONICAL_BRAND_MASTER)


def test_dual_control_still_applies_to_replacement_activation():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    with pytest.raises(L.LedgerError, match="DUAL CONTROL"):
        RES.resolve(RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
                    existing_events=[eu], actor_id=TECH,
                    actor_role=authz.BRAND_ADMIN, occurred_at=T2, reason="r",
                    new_asset="x.ai", new_scope=_sc(markets=["EU"]),
                    attestations=[_atts()[0]], checklist=_cl())
    # ...and one person wearing both hats is still one person
    with pytest.raises(L.LedgerError, match="DIFFERENT people"):
        RES.resolve(RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
                    existing_events=[eu], actor_id=TECH,
                    actor_role=authz.BRAND_ADMIN, occurred_at=T2, reason="r",
                    new_asset="x.ai", new_scope=_sc(markets=["EU"]),
                    attestations=_atts(TECH, TECH), checklist=_cl())


def test_a_conflict_cannot_be_resolved_by_machine_inference():
    with pytest.raises(C.HumanOnlyStateViolation):
        RES.machine_may_not_resolve()


def test_system_admin_may_not_supersede_a_master():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    with pytest.raises(RES.ResolutionError, match="unauthorized"):
        RES.resolve(RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
                    existing_events=[eu], actor_id="sa",
                    actor_role=authz.SYSTEM_ADMIN, occurred_at=T2, reason="r",
                    new_asset="x.ai", new_scope=_sc(markets=["EU"]),
                    attestations=_atts(), checklist=_cl())


def test_no_permission_is_activated_by_conflict_resolution():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    _, rec = RES.resolve(
        RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
        existing_events=[eu], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
        occurred_at=T2, reason="r", new_asset="eu2.ai",
        new_scope=_sc(markets=["EU"]), attestations=_atts(), checklist=_cl(),
        dry_run=True)
    proj = CR.project([eu] + rec["constituents"], now=NOW)
    for eff in proj["effective_permissions"].values():
        assert all(p["value"] is False for p in eff["permissions"].values())
    assert rec["resulting_scopes"]["grants_permissions"] is False


# === taxonomy version pinning ================================================
def test_a_decision_records_the_taxonomy_it_was_made_under():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    assert eu["canonical"]["scope"]["taxonomy_version"] == TX.version()


def test_a_taxonomy_change_does_not_silently_reinterpret_an_old_approval():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    eu["canonical"]["scope"]["taxonomy_version"] = "0.9.0"      # an older decision
    drift = CR.taxonomy_drift([eu])
    assert len(drift) == 1
    assert drift[0]["state"] == CR.TAXONOMY_REVIEW_REQUIRED
    assert drift[0]["pinned_taxonomy_version"] == "0.9.0"


# === the read model ==========================================================
def test_the_read_model_never_writes(tmp_path):
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    fr = _activate("fr.ai", _sc(markets=["FR"]), at=T2)
    before = sorted(p.name for p in L.LEDGER_ROOT.rglob("*.json"))
    CR.project([eu, fr], now=NOW, query_scopes=[_sc(markets=["FR"])])
    CR.conflicts([eu, fr])
    CR.canonical_for([eu, fr], _sc())
    assert sorted(p.name for p in L.LEDGER_ROOT.rglob("*.json")) == before


def test_the_projection_is_deterministic():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    fr = _activate("fr.ai", _sc(markets=["FR"]), at=T2)
    assert CR.masters([eu, fr]) == CR.masters([fr, eu])
    assert CR.conflicts([eu, fr]) == CR.conflicts([fr, eu])


# === queues ==================================================================
def test_review_queues_are_deterministic():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    fr = _activate("fr.ai", _sc(markets=["FR"]), at=T2)
    a = RV.build([eu, fr], now=NOW, nominations=[{"asset": "logo.pdf"}])
    b = RV.build([fr, eu], now=NOW, nominations=[{"asset": "logo.pdf"}])
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_canonical_and_conflict_queues_are_never_batch_approved():
    q = RV.build([], now=NOW)
    for key in ("A", "B", "C"):
        assert q["queues"][key]["batch_review_allowed"] is False
    assert q["never_batch_approved"] == ["A", "B", "C"]


def test_an_active_conflict_is_critical():
    eu = _activate("eu.ai", _sc(markets=["EU"]))
    fr = _activate("fr.ai", _sc(markets=["FR"]), at=T2)
    q = RV.build([eu, fr], now=NOW)
    assert q["queues"]["B"]["priority"] == RV.CRITICAL
    assert q["queues"]["B"]["count"] == 1
    assert "B" in q["critical"]


def test_every_queue_records_its_reason_and_roles():
    q = RV.build([], now=NOW)
    for key, item in q["queues"].items():
        assert item["shared_reason"].strip(), key
        assert item["required_reviewer_roles"], key
        assert item["recommended_next_action"].strip(), key
        assert item["priority"] in (RV.CRITICAL, RV.HIGH, RV.MEDIUM, RV.LOW)


# === the pilot ===============================================================
def test_the_pilot_holds_every_invariant_and_writes_nothing_real():
    p = run_c3b4.build_pilot()
    assert p["disjoint"]["conflicts"] == 0
    assert p["proven_conflict"]["count"] == 1
    assert p["scope_local"]["us_still_usable"] is True
    assert p["uncertain"]["proven"] is False
    assert p["supersession"]["post_conflicts"] == 0
    assert p["narrowing"]["after"] == ["FR"]
    assert p["nothing_written_on_failure"] is True
    assert p["no_permission_granted"] is True
    assert p["queues"]["deterministic"] is True
    assert not any(a["reason"].startswith("NOT REFUSED") for a in p["refused"])


def test_the_real_ledger_and_compound_store_stay_empty():
    from tools.dip0c import ledger_store as LS
    assert LS.validate()["counts"]["events"] == 0
    report = CP.validate_committed()
    assert report["compound_events"] == 0
    assert report["valid"]
