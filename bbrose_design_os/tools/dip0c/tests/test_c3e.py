"""DIP-0C3e — domain-aware conflict resolution (palette + master)."""
from __future__ import annotations

import pytest

from tools.dip0c import authz
from tools.dip0c import canonical_master as CM
from tools.dip0c import canonical_read as CR
from tools.dip0c import canonical_scope as S
from tools.dip0c import compound as CP
from tools.dip0c import config as C
from tools.dip0c import conflict_resolution as RES
from tools.dip0c import ledger as L
from tools.dip0c import palette_approval as PA
from tools.dip0c import permissions as P

T = "2026-07-14T09:00:00+00:00"
T2 = "2026-07-14T12:00:00+00:00"
NOW = "2026-07-14T13:00:00+00:00"
COLOR, LEGAL = "alice", "bob"

AUDIT = {"parse_status": "PARTIAL_PARSE", "fallback_used": True,
         "layout": ["NON_STANDARD_NAME_ENCODING"],
         "parser_warnings": ["NAME_LENGTH_FIELD_ABSENT"],
         "third_party_naming": ["PANTONE"], "swatch_names": ["Plum"],
         "color_models": ["RGB"], "color_types": ["GLOBAL"],
         "contains_spot_identity": False}
ACK_PARSER = {"parser_limitation_acknowledged": True, "reason": "eyes open"}
ACK_NAMING = {"acknowledged": True, "reason": "reviewed"}


def _p_atts(color=COLOR, legal=LEGAL):
    return [PA.attestation(PA.ATT_COLOR, actor_id=color,
                           actor_role=authz.BRAND_ADMIN, attested_at=T),
            PA.attestation(PA.ATT_RIGHTS, actor_id=legal,
                           actor_role=authz.LEGAL_REVIEWER, attested_at=T)]


def _p_cl(color=COLOR, legal=LEGAL):
    cl = PA.blank_checklist()
    for k in cl:
        by = color if k in PA.COLOR_ITEMS else legal
        cl[k] = {"result": True, "confirmed_by": by, "confirmed_at": T, "notes": ""}
    return cl


def _palette(asset, scope, at=T):
    return L.event(asset, event_type=L.BRAND_PALETTE_APPROVED, actor_id=COLOR,
                   actor_role=authz.BRAND_ADMIN, occurred_at=at, decision_reason="r",
                   canonical=PA.canonical_block(
                       PA.APPROVED_BRAND_PALETTE, scope=scope, checklist=_p_cl(),
                       attestations=_p_atts(), parser_audit=AUDIT,
                       value_provenance={"Plum": PA.DERIVED_PREVIEW},
                       parser_limitation_ack=ACK_PARSER,
                       third_party_ack=ACK_NAMING))


def _m_atts():
    return [CM.attestation(CM.ATT_TECHNICAL, actor_id=COLOR,
                           actor_role=authz.BRAND_ADMIN, attested_at=T),
            CM.attestation(CM.ATT_LEGAL, actor_id=LEGAL,
                           actor_role=authz.LEGAL_REVIEWER, attested_at=T)]


def _m_cl():
    cl = CM.blank_checklist()
    for k in cl:
        by = COLOR if k in CM.TECHNICAL_ITEMS else LEGAL
        cl[k] = {"result": True, "confirmed_by": by, "confirmed_at": T, "notes": ""}
    return cl


def _master(asset, scope, at=T):
    return L.event(asset, event_type=L.CANONICAL_MASTER_APPROVED, actor_id=COLOR,
                   actor_role=authz.BRAND_ADMIN, occurred_at=at, decision_reason="r",
                   canonical=L.canonical_block(
                       C.CANONICAL_BRAND_MASTER, scope=scope, checklist=_m_cl(),
                       attestations=_m_atts(),
                       authority_domain=L.DOMAIN_BRAND_MASTER))


def _sc(**kw):
    return S.scope("BBROSE", **kw)


def _supersede(events, incumbent, **kw):
    args = dict(incumbent_event_id=incumbent["event_id"], existing_events=events,
                actor_id=COLOR, actor_role=authz.BRAND_ADMIN, occurred_at=T2,
                reason="a new palette", new_asset="c.ase",
                new_scope=_sc(markets=["EU"]), attestations=_p_atts(),
                checklist=_p_cl(), palette_audit=AUDIT,
                value_provenance={"Plum": PA.RAW_SOURCE},
                parser_limitation_ack=ACK_PARSER, third_party_ack=ACK_NAMING,
                dry_run=True)
    args.update(kw)
    return RES.resolve(RES.SUPERSEDE_INCUMBENT, **args)


# === the shared contract =====================================================
def test_every_domain_maps_every_action():
    for domain, spec in RES.DOMAIN_SPEC.items():
        assert set(spec["authz"]) == set(RES.ACTIONS), domain
    assert set(RES.DOMAIN_SPEC) == set(L.AUTHORITY_DOMAINS)


def test_the_domain_is_read_from_the_incumbent_not_supplied_by_the_caller():
    """A resolution operates on the authority that actually exists."""
    p = _palette("a.ase", _sc(markets=["EU"]))
    _, rec = RES.resolve(RES.DEPRECATE_INCUMBENT,
                         incumbent_event_id=p["event_id"], existing_events=[p],
                         actor_id=COLOR, actor_role=authz.BRAND_ADMIN,
                         occurred_at=T2, reason="retired", dry_run=True)
    assert rec["authority_domain"] == L.DOMAIN_BRAND_PALETTE


def test_a_palette_resolution_never_emits_brand_master_event_types():
    p = _palette("a.ase", _sc(markets=["EU"]))
    _, rec = _supersede([p], p)
    kinds = [e["event_type"] for e in rec["constituents"]]
    assert kinds == [L.PALETTE_DEPRECATED, L.PALETTE_SUPERSEDED]
    assert not any("CANONICAL_MASTER" in k for k in kinds)
    assert not any(k in (L.VARIANT_RECLASSIFIED, L.ASSET_QUARANTINED)
                   for k in kinds)


def test_a_master_resolution_never_emits_palette_event_types():
    m = _master("logo.ai", _sc(markets=["EU"]))
    _, rec = RES.resolve(
        RES.SUPERSEDE_INCUMBENT, incumbent_event_id=m["event_id"],
        existing_events=[m], actor_id=COLOR, actor_role=authz.BRAND_ADMIN,
        occurred_at=T2, reason="v2", new_asset="logo2.ai",
        new_scope=_sc(markets=["EU"]), attestations=_m_atts(), checklist=_m_cl(),
        dry_run=True)
    kinds = [e["event_type"] for e in rec["constituents"]]
    assert kinds == [L.CANONICAL_MASTER_DEPRECATED, L.CANONICAL_MASTER_REPLACED]
    assert not any(k in L.PALETTE_EVENTS for k in kinds)
    assert rec["authority_domain"] == L.DOMAIN_BRAND_MASTER


# === conflict, then resolution ================================================
def test_two_overlapping_active_palettes_fail_closed():
    sc = _sc(markets=["EU"])
    ev = [_palette("a.ase", sc), _palette("b.ase", sc, at=T2)]
    c = CR.conflicts(ev)
    assert len(c) == 1
    assert c[0]["authority_domain"] == L.DOMAIN_BRAND_PALETTE
    q = CR.canonical_for(ev, sc, L.DOMAIN_BRAND_PALETTE)
    assert q["state"] == CR.CANONICAL_CONFLICT
    assert q["usable"] is False           # NEITHER is available for the scope


def test_deprecating_the_incumbent_resolves_the_conflict():
    sc = _sc(markets=["EU"])
    a, b = _palette("a.ase", sc), _palette("b.ase", sc, at=T2)
    _, rec = RES.resolve(RES.DEPRECATE_INCUMBENT, incumbent_event_id=a["event_id"],
                         existing_events=[a, b], actor_id=COLOR,
                         actor_role=authz.BRAND_ADMIN, occurred_at=T2,
                         reason="a.ase retired", dry_run=True)
    post = [a, b] + rec["constituents"]
    assert CR.conflicts(post) == []
    assert {m["asset"]: m["lifecycle"] for m in CR.masters(post)} == {
        "a.ase": CR.DEPRECATED, "b.ase": CR.ACTIVE}
    assert CR.canonical_for(post, sc, L.DOMAIN_BRAND_PALETTE)["asset"] == "b.ase"


def test_supersession_links_incumbent_and_successor():
    sc = _sc(markets=["EU"])
    a = _palette("a.ase", sc)
    _, rec = _supersede([a], a)
    post = [a] + rec["constituents"]
    ms = {m["asset"]: m for m in CR.masters(post)}
    assert ms["a.ase"]["lifecycle"] == CR.SUPERSEDED
    assert ms["a.ase"]["superseded_by"]["asset"] == "c.ase"
    assert ms["c.ase"]["lifecycle"] == CR.ACTIVE
    assert CR.conflicts(post) == []
    chains = CR._chains(CR.masters(post))
    assert chains[0]["from_asset"] == "a.ase" and chains[0]["to_asset"] == "c.ase"


def test_a_resolution_that_would_leave_an_overlap_is_refused():
    """Superseding ONE of two conflicting palettes with a THIRD leaves an overlap."""
    sc = _sc(markets=["EU"])
    a, b = _palette("a.ase", sc), _palette("b.ase", sc, at=T2)
    with pytest.raises(CP.CompoundError, match="two active canonical masters"):
        _supersede([a, b], a, dry_run=False)


# === dual control survives the palette conflict path ==========================
def test_palette_supersession_requires_dual_control():
    a = _palette("a.ase", _sc(markets=["EU"]))
    with pytest.raises(L.LedgerError, match="DUAL CONTROL"):
        _supersede([a], a, attestations=[_p_atts()[0]])


def test_the_same_actor_cannot_satisfy_both_palette_attestations():
    a = _palette("a.ase", _sc(markets=["EU"]))
    with pytest.raises(L.LedgerError, match="DIFFERENT people"):
        _supersede([a], a, attestations=_p_atts(COLOR, COLOR))


def test_a_missing_legal_attestation_appends_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(CP, "COMPOUND_DIR", tmp_path / "compound")
    a = _palette("a.ase", _sc(markets=["EU"]))
    before = sorted(p.name for p in tmp_path.rglob("*"))
    with pytest.raises((L.LedgerError, CP.CompoundError, RES.ResolutionError)):
        _supersede([a], a, attestations=[_p_atts()[0]], dry_run=False)
    assert sorted(p.name for p in tmp_path.rglob("*")) == before


def test_system_admin_may_not_resolve_a_palette_conflict():
    a = _palette("a.ase", _sc(markets=["EU"]))
    with pytest.raises(RES.ResolutionError, match="unauthorized"):
        _supersede([a], a, actor_id="sa", actor_role=authz.SYSTEM_ADMIN)


def test_a_machine_may_not_resolve_a_conflict():
    with pytest.raises(C.HumanOnlyStateViolation):
        RES.machine_may_not_resolve()


# === palette-specific safeguards ==============================================
def test_a_replacement_must_carry_its_own_technical_audit():
    a = _palette("a.ase", _sc(markets=["EU"]))
    with pytest.raises(RES.ResolutionError, match="technical audit"):
        _supersede([a], a, palette_audit=None)


def test_a_replacement_must_declare_value_provenance():
    a = _palette("a.ase", _sc(markets=["EU"]))
    with pytest.raises(RES.ResolutionError, match="provenance"):
        _supersede([a], a, value_provenance={})


def test_the_parser_limitation_survives_the_replacement():
    """A deprecation must not quietly clean up the incumbent's history."""
    a = _palette("a.ase", _sc(markets=["EU"]))
    _, rec = _supersede([a], a)
    carried = rec["constituents"][0]["canonical"]["palette"]
    assert carried["parse_status"] == "PARTIAL_PARSE"
    assert carried["fallback_used"] is True
    assert carried["parser_warnings"] == ["NAME_LENGTH_FIELD_ABSENT"]
    assert carried["layout"] == ["NON_STANDARD_NAME_ENCODING"]
    # ...and the NEW palette carries its own audit, warnings intact
    new = rec["constituents"][1]["canonical"]["palette"]
    assert new["parse_status"] == "PARTIAL_PARSE"
    assert new["parser_warnings"] == ["NAME_LENGTH_FIELD_ABSENT"]


def test_the_third_party_acknowledgement_survives_the_replacement():
    a = _palette("a.ase", _sc(markets=["EU"]))
    _, rec = _supersede([a], a)
    carried = rec["constituents"][0]["canonical"]["palette"]
    assert carried["third_party_naming"] == ["PANTONE"]
    assert carried["third_party_naming_acknowledged"]["acknowledged"] is True
    assert carried["third_party_naming_acknowledged"]["reason"]


def test_a_derived_preview_is_not_converted_into_source_truth():
    """The incumbent said DERIVED_PREVIEW. Retiring it does not promote the value."""
    a = _palette("a.ase", _sc(markets=["EU"]))
    _, rec = _supersede([a], a)
    carried = rec["constituents"][0]["canonical"]["palette"]
    assert carried["value_provenance"] == {"Plum": PA.DERIVED_PREVIEW}


def test_a_resolution_grants_no_operational_permission():
    a = _palette("a.ase", _sc(markets=["EU"]))
    _, rec = _supersede([a], a)
    for e in rec["constituents"]:
        assert e["canonical"]["palette"]["grants_permissions"] is False
    eff = P.effective_permissions("c.ase", [a] + rec["constituents"], now=NOW)
    assert not any(r["value"] for r in eff["permissions"].values())
    assert rec["resulting_scopes"]["grants_permissions"] is False


# === narrowing / widening =====================================================
def test_palette_narrowing_reduces_scope_only():
    a = _palette("a.ase", _sc(markets=["EU"]))
    _, rec = RES.resolve(RES.NARROW_INCUMBENT_SCOPE,
                         incumbent_event_id=a["event_id"], existing_events=[a],
                         actor_id=COLOR, actor_role=authz.BRAND_ADMIN,
                         occurred_at=T2, reason="France only",
                         narrowed_scope=_sc(markets=["FR"]), dry_run=True)
    assert rec["constituents"][0]["event_type"] == L.SCOPE_REDUCED
    assert rec["constituents"][0]["canonical"]["authority_domain"] \
        == L.DOMAIN_BRAND_PALETTE
    m = CR.masters([a] + rec["constituents"])[0]
    assert m["scope"]["markets"]["tokens"] == ["FR"]
    assert m["authority_domain"] == L.DOMAIN_BRAND_PALETTE


def test_palette_widening_requires_a_complete_reapproval():
    a = _palette("a.ase", _sc(markets=["EU"]))
    with pytest.raises(RES.ResolutionError, match="WIDENS"):
        RES.resolve(RES.NARROW_INCUMBENT_SCOPE, incumbent_event_id=a["event_id"],
                    existing_events=[a], actor_id=COLOR,
                    actor_role=authz.BRAND_ADMIN, occurred_at=T2, reason="r",
                    narrowed_scope=_sc(markets=["EU", "US"]))


def test_a_palette_variant_cannot_silently_become_the_brand_palette():
    a = _palette("a.ase", _sc(markets=["EU"]))
    with pytest.raises(RES.ResolutionError, match="dual control"):
        RES.resolve(RES.RECLASSIFY_AS_VARIANT, incumbent_event_id=a["event_id"],
                    existing_events=[a], actor_id=COLOR,
                    actor_role=authz.BRAND_ADMIN, occurred_at=T2, reason="r",
                    variant_state=PA.APPROVED_BRAND_PALETTE)


def test_a_resolution_never_reaches_across_domains():
    sc = _sc(markets=["EU"])
    a, m = _palette("a.ase", sc), _master("logo.ai", sc)
    with pytest.raises(RES.ResolutionError, match="never reaches across domains"):
        RES.resolve(RES.NARROW_NEW_SCOPE, incumbent_event_id=a["event_id"],
                    existing_events=[a, m], actor_id=COLOR,
                    actor_role=authz.BRAND_ADMIN, occurred_at=T2, reason="r",
                    new_asset="logo.ai", narrowed_scope=_sc(markets=["FR"]))


# === isolation ================================================================
def test_a_palette_resolution_leaves_brand_master_authority_untouched():
    sc = _sc(markets=["EU"])
    m = _master("logo.ai", sc)
    a, b = _palette("a.ase", sc), _palette("b.ase", sc, at=T2)
    _, rec = RES.resolve(RES.DEPRECATE_INCUMBENT, incumbent_event_id=a["event_id"],
                         existing_events=[m, a, b], actor_id=COLOR,
                         actor_role=authz.BRAND_ADMIN, occurred_at=T2,
                         reason="retired", dry_run=True)
    post = [m, a, b] + rec["constituents"]
    master = CR.canonical_for(post, sc, L.DOMAIN_BRAND_MASTER)
    assert master["asset"] == "logo.ai"
    assert master["usable"] is True
    assert CR.canonical_for(post, sc, L.DOMAIN_BRAND_PALETTE)["asset"] == "b.ase"


# === the atomic write =========================================================
def test_a_palette_resolution_commits_atomically_and_round_trips(tmp_path,
                                                                 monkeypatch):
    """The write path, ACTUALLY RUN — not dry_run."""
    monkeypatch.setattr(CP, "COMPOUND_DIR", tmp_path / "compound")
    sc = _sc(markets=["EU"])
    a, b = _palette("a.ase", sc), _palette("b.ase", sc, at=T2)
    path, rec = RES.resolve(RES.DEPRECATE_INCUMBENT,
                            incumbent_event_id=a["event_id"],
                            existing_events=[a, b], actor_id=COLOR,
                            actor_role=authz.BRAND_ADMIN, occurred_at=T2,
                            reason="a.ase retired")
    assert path.exists()
    assert not list((tmp_path / "compound").glob("*.tmp"))

    loaded = CP.load_all()
    assert len(loaded) == 1
    assert loaded[0]["authority_domain"] == L.DOMAIN_BRAND_PALETTE
    assert loaded[0]["compound_content_hash"] == CP.content_hash(loaded[0])

    post = [a, b] + CP.expand()
    assert CR.conflicts(post) == []
    assert CR.canonical_for(post, sc, L.DOMAIN_BRAND_PALETTE)["asset"] == "b.ase"
    assert CP.validate_committed()["valid"]

    # the retired palette's audit survived the round-trip through JSON
    carried = CP.expand()[0]["canonical"]["palette"]
    assert carried["parse_status"] == "PARTIAL_PARSE"
    assert carried["parser_warnings"] == ["NAME_LENGTH_FIELD_ABSENT"]


def test_a_failed_palette_resolution_leaves_the_ledger_byte_identical(tmp_path,
                                                                      monkeypatch):
    monkeypatch.setattr(CP, "COMPOUND_DIR", tmp_path / "compound")
    (tmp_path / "compound").mkdir()
    a = _palette("a.ase", _sc(markets=["EU"]))
    before = {p.name: p.read_bytes() for p in (tmp_path / "compound").rglob("*")}
    with pytest.raises((RES.ResolutionError, CP.CompoundError, L.LedgerError)):
        _supersede([a], a, palette_audit=None, dry_run=False)
    after = {p.name: p.read_bytes() for p in (tmp_path / "compound").rglob("*")}
    assert after == before


def test_the_real_ledger_stays_empty():
    from tools.dip0c import ledger_store as LS
    r = LS.validate()
    assert r["counts"]["events"] == 0
    assert r["counts"]["compound_events"] == 0
    assert r["valid"]
