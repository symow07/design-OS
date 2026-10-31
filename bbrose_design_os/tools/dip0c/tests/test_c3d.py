"""DIP-0C3d — palette decisions, authority domains, media scope, C3 queues."""
from __future__ import annotations

import json

import pytest

from tools.dip0c import ase
from tools.dip0c import authz
from tools.dip0c import canonical_master as CM
from tools.dip0c import canonical_read as CR
from tools.dip0c import canonical_scope as S
from tools.dip0c import color_compare as CC
from tools.dip0c import config as C
from tools.dip0c import ledger as L
from tools.dip0c import palette as PAL
from tools.dip0c import palette_approval as PA
from tools.dip0c import permissions as P
from tools.dip0c import review_c3 as RV
from tools.dip0c import rights_model as RM
from tools.dip0c import run_c3d
from tools.dip0c import taxonomy as TX

T = "2026-07-14T09:00:00+00:00"
T2 = "2026-07-14T12:00:00+00:00"
NOW = "2026-07-14T13:00:00+00:00"
COLOR, LEGAL = "alice", "bob"

AUDIT_OK = {"parse_status": ase.TECHNICALLY_PARSED, "fallback_used": False,
            "layout": [ase.LAYOUT_STANDARD], "parser_warnings": [],
            "third_party_naming": [], "swatch_names": ["Plum"],
            "color_models": ["RGB"], "color_types": ["GLOBAL"],
            "contains_spot_identity": False}
AUDIT_REAL = {**AUDIT_OK, "parse_status": ase.PARTIAL_PARSE, "fallback_used": True,
              "layout": [ase.LAYOUT_NON_STANDARD],
              "parser_warnings": [ase.W_NAME_LENGTH_ABSENT],
              "third_party_naming": ["PANTONE"],
              "swatch_names": ["Pantone 3519 C"]}


def _atts(color=COLOR, legal=LEGAL, legal_role=authz.LEGAL_REVIEWER):
    return [PA.attestation(PA.ATT_COLOR, actor_id=color,
                           actor_role=authz.BRAND_ADMIN, attested_at=T),
            PA.attestation(PA.ATT_RIGHTS, actor_id=legal,
                           actor_role=legal_role, attested_at=T)]


def _cl(color=COLOR, legal=LEGAL):
    cl = PA.blank_checklist()
    for k in cl:
        by = color if k in PA.COLOR_ITEMS else legal
        cl[k] = {"result": True, "confirmed_by": by, "confirmed_at": T, "notes": ""}
    return cl


def _ev(asset):
    e = L.evidence(asset, evidence_type="CONTRACT", title="t", submitted_by=LEGAL,
                   actor_role=authz.LEGAL_REVIEWER, submitted_at=T)
    e["review_status"] = L.EV_ACCEPTED
    e["reviewed_by"] = LEGAL
    return e


def _approve(asset="p.ase", **kw):
    kw.setdefault("requested_state", PA.APPROVED_BRAND_PALETTE)
    kw.setdefault("actor_role", authz.BRAND_ADMIN)
    kw.setdefault("actor_id", COLOR)
    kw.setdefault("checklist", _cl())
    kw.setdefault("attestations", _atts())
    kw.setdefault("parser_audit", AUDIT_OK)
    kw.setdefault("ownership_state", C.OWN_BBROSE_CONFIRMED)
    kw.setdefault("license_state", C.LIC_APPROVED)
    kw.setdefault("evidence_records", [_ev(asset)])
    kw.setdefault("reason", "test")
    kw.setdefault("value_provenance", {"Plum": PA.RAW_SOURCE})
    kw.setdefault("requested_scope", S.scope("BBROSE"))
    return PA.check_approval(asset, **kw)


def _m_cl():
    cl = CM.blank_checklist()
    for k in cl:
        by = COLOR if k in CM.TECHNICAL_ITEMS else LEGAL
        cl[k] = {"result": True, "confirmed_by": by, "confirmed_at": T, "notes": ""}
    return cl


def _m_atts():
    return [CM.attestation(CM.ATT_TECHNICAL, actor_id=COLOR,
                           actor_role=authz.BRAND_ADMIN, attested_at=T),
            CM.attestation(CM.ATT_LEGAL, actor_id=LEGAL,
                           actor_role=authz.LEGAL_REVIEWER, attested_at=T)]


def _master(asset, scope, at=T):
    return L.event(asset, event_type=L.CANONICAL_MASTER_APPROVED, actor_id=COLOR,
                   actor_role=authz.BRAND_ADMIN, occurred_at=at, decision_reason="r",
                   canonical=L.canonical_block(
                       C.CANONICAL_BRAND_MASTER, scope=scope, checklist=_m_cl(),
                       attestations=_m_atts(),
                       authority_domain=L.DOMAIN_BRAND_MASTER))


def _palette(asset, scope, at=T, audit=None):
    return L.event(asset, event_type=L.BRAND_PALETTE_APPROVED, actor_id=COLOR,
                   actor_role=authz.BRAND_ADMIN, occurred_at=at, decision_reason="r",
                   canonical=PA.canonical_block(
                       PA.APPROVED_BRAND_PALETTE, scope=scope, checklist=_cl(),
                       attestations=_atts(), parser_audit=audit or AUDIT_OK,
                       value_provenance={"Plum": PA.RAW_SOURCE}))


# === the machine may never approve ===========================================
@pytest.mark.parametrize("state", PA.HUMAN_ONLY_PALETTE)
def test_a_machine_can_never_approve_a_palette(state):
    with pytest.raises(C.HumanOnlyStateViolation):
        PA.machine_palette_authority(state)


def test_system_admin_may_not_approve_or_attest_a_palette():
    for action in (authz.APPROVE_BRAND_PALETTE, authz.ATTEST_PALETTE_COLOR,
                   authz.ATTEST_PALETTE_RIGHTS, authz.CONFIRM_PALETTE_ASSOCIATION):
        assert action in authz.SYSTEM_ADMIN_FORBIDDEN
        with pytest.raises(authz.NotAuthorized):
            authz.authorize(authz.SYSTEM_ADMIN, action, actor_id="sa")


def test_final_activation_is_brand_admin_only():
    assert authz.POLICY[authz.APPROVE_BRAND_PALETTE] == (authz.BRAND_ADMIN,)
    for role in (authz.DESIGN_REVIEWER, authz.LEGAL_REVIEWER, authz.BUSINESS_OWNER,
                 authz.SYSTEM_ADMIN, authz.OBSERVER):
        with pytest.raises(authz.NotAuthorized):
            authz.authorize(role, authz.APPROVE_BRAND_PALETTE, actor_id="x")


# === dual control ============================================================
def test_palette_approval_requires_two_distinct_actors():
    ok, problems = _approve(checklist=_cl(COLOR, COLOR),
                            attestations=_atts(COLOR, COLOR))
    assert not ok
    assert any("two DIFFERENT people" in p or "BOTH halves" in p for p in problems)


def test_one_actor_holding_several_roles_cannot_satisfy_both_attestations():
    """color_reviewer_id != legal_reviewer_id. Two hats, one person, no."""
    ok, problems = _approve(actor_id="carol", checklist=_cl("carol", "carol"),
                            attestations=_atts("carol", "carol"))
    assert not ok
    assert any("color_reviewer_id != legal_reviewer_id" in p for p in problems)


def test_the_rights_attestation_is_legal_reviewers_alone():
    ok, problems = _approve(attestations=_atts(legal_role=authz.BRAND_ADMIN))
    assert not ok
    assert any("RIGHTS_AND_USE" in p and "may NOT" in p for p in problems)


def test_either_attestation_alone_is_blocked():
    for i, missing in ((0, "RIGHTS_AND_USE"), (1, "COLOR_AND_BRAND")):
        ok, problems = _approve(attestations=[_atts()[i]])
        assert not ok
        assert any(f"the {missing} attestation is missing" in p for p in problems)


def test_the_ledger_refuses_a_single_actor_palette_approval():
    with pytest.raises(L.LedgerError, match="DIFFERENT people"):
        L.event("p.ase", event_type=L.BRAND_PALETTE_APPROVED, actor_id=COLOR,
                actor_role=authz.BRAND_ADMIN, occurred_at=T, decision_reason="solo",
                canonical=PA.canonical_block(
                    PA.APPROVED_BRAND_PALETTE, scope=S.scope("BBROSE"),
                    checklist=_cl(COLOR, COLOR), attestations=_atts(COLOR, COLOR),
                    parser_audit=AUDIT_OK, value_provenance={}))


def test_brand_palette_approval_is_under_dual_control():
    assert L.BRAND_PALETTE_APPROVED in L.DUAL_CONTROL_EVENTS
    assert L.PALETTE_SUPERSEDED in L.DUAL_CONTROL_EVENTS


# === the six independent questions ===========================================
def test_parser_success_does_not_grant_palette_approval():
    """Technically perfect, and still refused on rights."""
    ok, problems = _approve(ownership_state=C.OWN_UNKNOWN,
                            license_state=C.LIC_UNVERIFIED, evidence_records=[])
    assert AUDIT_OK["parse_status"] == ase.TECHNICALLY_PARSED
    assert not ok
    assert any("ownership" in p for p in problems)


def test_palette_approval_grants_no_operational_permissions():
    """THE test: approved as the brand palette, and every permission still false."""
    evt = _palette("p.ase", S.scope("BBROSE"))
    eff = P.effective_permissions("p.ase", [evt], now=NOW)
    assert all(r["value"] is False for r in eff["permissions"].values())
    assert all(r["status"] == C.EFF_DENIED_NO_GRANT
               for r in eff["permissions"].values())
    assert evt["canonical"]["palette"]["grants_permissions"] is False


def test_ownership_confirmation_grants_no_palette_permission():
    own = L.event("p.ase", event_type=L.PALETTE_OWNERSHIP_CONFIRMED, actor_id=LEGAL,
                  actor_role=authz.LEGAL_REVIEWER, occurred_at=T,
                  decision_reason="ours")
    eff = P.effective_permissions("p.ase", [own], now=NOW)
    assert not any(r["value"] for r in eff["permissions"].values())


def test_the_canonical_permission_set_is_reused_not_duplicated():
    assert P.FLAGS is RM.PERMISSION_FLAGS
    assert set(PA.CHECKLIST) & set(RM.PERMISSION_FLAGS) == set()   # no shadow copy


def test_no_permission_count_is_hardcoded():
    q = RV.build([], now=NOW)
    assert q["permission_flag_count"] == len(RM.PERMISSION_FLAGS)
    assert q["permission_flags"] == sorted(RM.PERMISSION_FLAGS)


# === the parser limitation survives approval =================================
def test_a_fallback_parsed_palette_needs_an_explicit_acknowledgement():
    ok, problems = _approve(parser_audit=AUDIT_REAL,
                            value_provenance={"Pantone 3519 C": PA.RAW_SOURCE},
                            third_party_ack={"acknowledged": True, "reason": "r"})
    assert not ok
    assert any("acknowledge the parser limitation" in p for p in problems)


def test_acknowledging_a_parser_limitation_requires_a_reason():
    ok, problems = _approve(
        parser_audit=AUDIT_REAL,
        value_provenance={"Pantone 3519 C": PA.RAW_SOURCE},
        parser_limitation_ack={"parser_limitation_acknowledged": True, "reason": " "},
        third_party_ack={"acknowledged": True, "reason": "r"})
    assert not ok
    assert any("requires a reason" in p for p in problems)


def test_the_parser_limitation_survives_the_approval():
    """Approving a file does not make it well-formed."""
    blk = PA.approval_block(
        AUDIT_REAL, value_provenance={"Pantone 3519 C": PA.DERIVED_PREVIEW},
        parser_limitation_ack={"parser_limitation_acknowledged": True,
                               "reason": "accepted with eyes open"},
        third_party_ack={"acknowledged": True, "reason": "r"})
    assert blk["parse_status"] == ase.PARTIAL_PARSE
    assert blk["fallback_used"] is True
    assert blk["layout"] == [ase.LAYOUT_NON_STANDARD]
    assert ase.W_NAME_LENGTH_ABSENT in blk["parser_warnings"]
    assert blk["contains_spot_identity"] is False
    assert blk["value_provenance"]["Pantone 3519 C"] == PA.DERIVED_PREVIEW
    assert "does not rewrite" in blk["note"]


def test_third_party_naming_must_be_acknowledged():
    ok, problems = _approve(
        parser_audit=AUDIT_REAL,
        value_provenance={"Pantone 3519 C": PA.RAW_SOURCE},
        parser_limitation_ack={"parser_limitation_acknowledged": True, "reason": "r"})
    assert not ok
    assert any("third-party naming detected" in p for p in problems)


def test_every_approved_value_must_declare_its_provenance():
    ok, problems = _approve(value_provenance={})
    assert not ok
    assert any("declare its provenance" in p for p in problems)
    assert set(PA.PROVENANCE) == {PA.RAW_SOURCE, PA.DERIVED_PREVIEW,
                                  PA.MANUALLY_CONFIRMED}


# === authority domains =======================================================
def test_a_brand_master_and_a_brand_palette_do_not_conflict():
    """They answer DIFFERENT questions. Same scope, no contradiction."""
    sc = S.scope("BBROSE", markets=["EU"])
    ev = [_master("logo.ai", sc), _palette("p.ase", sc)]
    assert CR.conflicts(ev) == []
    assert CR.canonical_for(ev, sc, L.DOMAIN_BRAND_MASTER)["asset"] == "logo.ai"
    assert CR.canonical_for(ev, sc, L.DOMAIN_BRAND_PALETTE)["asset"] == "p.ase"


def test_two_overlapping_brand_palettes_do_conflict():
    sc = S.scope("BBROSE", markets=["EU"])
    ev = [_palette("a.ase", sc), _palette("b.ase", sc, at=T2)]
    c = CR.conflicts(ev)
    assert len(c) == 1
    assert c[0]["authority_domain"] == L.DOMAIN_BRAND_PALETTE
    assert CR.canonical_for(ev, sc, L.DOMAIN_BRAND_PALETTE)["state"] \
        == CR.CANONICAL_CONFLICT


def test_a_palette_conflict_does_not_block_the_logo_master():
    sc = S.scope("BBROSE", markets=["EU"])
    ev = [_master("logo.ai", sc), _palette("a.ase", sc), _palette("b.ase", sc, at=T2)]
    assert CR.canonical_for(ev, sc, L.DOMAIN_BRAND_MASTER)["usable"] is True
    assert CR.canonical_for(ev, sc, L.DOMAIN_BRAND_PALETTE)["usable"] is False


def test_the_projection_separates_the_domains():
    sc = S.scope("BBROSE")
    proj = CR.project([_master("logo.ai", sc), _palette("p.ase", sc)], now=NOW)
    d = proj["authority_domains"]
    assert d[L.DOMAIN_BRAND_MASTER]["active"] == ["logo.ai"]
    assert d[L.DOMAIN_BRAND_PALETTE]["active"] == ["p.ase"]


# === media scope =============================================================
@pytest.mark.parametrize("a,b,want", [
    ("ALL", "PRINT", TX.OVERLAPPING),
    ("PRINT", "PACKAGING_PRINT", TX.OVERLAPPING),
    ("DIGITAL", "SCREEN", TX.OVERLAPPING),
    ("PRINT", "DIGITAL", TX.DISJOINT),
    ("DIGITAL", "PACKAGING_PRINT", TX.DISJOINT),      # inherited from PRINT/DIGITAL
    ("SCREEN", "WEB", TX.UNKNOWN),                    # NOT declared — do not guess
    ("WEB", "SOCIAL_MEDIA", TX.UNKNOWN),
])
def test_media_relations_are_declared_never_guessed(a, b, want):
    assert TX.relate_tokens("media", a, b)[0] == want


def test_media_is_independent_of_products():
    """Same product, different media -> disjoint. Product cannot answer for media."""
    a = S.scope("BBROSE", products=["LIP_GLOSS"], media=["PRINT"])
    b = S.scope("BBROSE", products=["LIP_GLOSS"], media=["DIGITAL"])
    assert S.relate(a, b)["relation"] == S.DISJOINT
    assert S.relate(a, b)["per_axis"]["products"] == S.IDENTICAL
    assert S.relate(a, b)["per_axis"]["media"] == S.DISJOINT


def _grant(media):
    return L.event("p.ase", event_type=L.PERMISSION_GRANTED, actor_id=LEGAL,
                   actor_role=authz.LEGAL_REVIEWER, occurred_at=T,
                   decision_reason="r",
                   permission=L.permission_block(
                       "retrieval_allowed", previous_value=False,
                       requested_value=True, purpose="p", approved_media=media))


def test_a_digital_approval_does_not_authorize_packaging_print():
    ev = [_grant(["DIGITAL"])]
    ok = P.effective_permissions("p.ase", ev, now=NOW,
                                 media="PACKAGING_PRINT")["permissions"]
    assert ok["retrieval_allowed"]["value"] is False
    assert ok["retrieval_allowed"]["status"] == C.EFF_DENIED_SCOPE


def test_a_digital_approval_covers_screen_because_the_taxonomy_says_so():
    ev = [_grant(["DIGITAL"])]
    r = P.effective_permissions("p.ase", ev, now=NOW, media="SCREEN")["permissions"]
    assert r["retrieval_allowed"]["value"] is True


def test_an_undeclared_media_relation_fails_closed():
    """WEB vs DIGITAL is UNKNOWN, and unknown must DENY."""
    ev = [_grant(["DIGITAL"])]
    r = P.effective_permissions("p.ase", ev, now=NOW, media="WEB")["permissions"]
    assert r["retrieval_allowed"]["value"] is False


def test_an_unregistered_media_token_fails_closed():
    ev = [_grant(["DIGITAL"])]
    r = P.effective_permissions("p.ase", ev, now=NOW,
                                media="HOLOGRAM")["permissions"]
    assert r["retrieval_allowed"]["value"] is False


# === backward compatibility ==================================================
def _v1_scope():
    return {"brand": "BBROSE", "lockup": S.axis_value("PRIMARY"),
            "products": S.axis_value(None), "markets": S.axis_value(["EU"]),
            "variant_role": S.axis_value("MASTER"), "period": S.period(),
            "taxonomy_version": "1.0.0"}


def test_a_v1_0_0_scope_normalizes_media_to_all_with_provenance():
    n = S.normalize_for_compare(_v1_scope())
    assert n["media"]["mode"] == S.MODE_ALL
    assert n["media"]["compatibility"] == S.COMPAT_MEDIA_NORMALIZED
    assert n["original_scope_taxonomy_version"] == "1.0.0"
    assert "media" not in _v1_scope()          # the ORIGINAL is untouched


def test_a_v1_0_0_scope_still_compares_correctly():
    assert S.relate(_v1_scope(),
                    S.scope("BBROSE", markets=["EU"]))["relation"] == S.IDENTICAL


def test_taxonomy_drift_stays_visible():
    m = _master("logo.ai", S.scope("BBROSE"))
    m["canonical"]["scope"]["taxonomy_version"] = "1.0.0"
    drift = CR.taxonomy_drift([m])
    assert len(drift) == 1
    assert drift[0]["state"] == CR.TAXONOMY_REVIEW_REQUIRED
    assert drift[0]["current_taxonomy_version"] == "1.1.0"


def test_new_decisions_pin_the_new_taxonomy():
    assert TX.version() == "1.1.0"
    assert S.scope("BBROSE")["taxonomy_version"] == "1.1.0"
    assert S.scope("BBROSE")["media"]["mode"] == S.MODE_ALL      # explicit ALL


def test_an_incomplete_media_axis_does_not_silently_become_all():
    inc = S.scope("BBROSE", incomplete_axes=("media",))
    assert inc["media"]["mode"] == S.MODE_INCOMPLETE
    assert S.relate(inc, S.scope("BBROSE", media=["PRINT"]))["relation"] == S.UNKNOWN


# === the colour-comparison gate ==============================================
def test_a_naive_cmyk_preview_may_not_enter_a_comparison():
    sw = {"raw": {"model": "CMYK", "channels": [0.1, 0.2, 0.3, 0.4],
                  "authoritative": True},
          "normalized": {"conversion_method": PAL.CONV_NAIVE_CMYK}}
    with pytest.raises(CC.ComparisonRefused, match="arithmetic gesture"):
        CC.refuse_naive_preview(sw)


def test_cross_model_comparison_is_refused():
    rgb = {"raw": {"model": "RGB", "channels": [0.5, 0.2, 0.4],
                   "authoritative": True}}
    cmyk = {"raw": {"model": "CMYK", "channels": [0, 0, 0, 1],
                    "authoritative": True}}
    with pytest.raises(CC.ComparisonRefused):
        CC.compare(rgb, cmyk)


def test_cmyk_comparison_requires_a_declared_icc_profile():
    cmyk = {"raw": {"model": "CMYK", "channels": [0, 0, 0, 1],
                    "authoritative": True}}
    assert CC.can_compare(cmyk, cmyk)["comparable"] is False
    assert CC.can_compare(cmyk, cmyk)["reason"] == CC.R_NO_ICC


def test_source_rgb_to_source_rgb_is_permitted():
    a = {"raw": {"model": "RGB", "channels": [0.5, 0.2, 0.4], "authoritative": True}}
    b = {"raw": {"model": "RGB", "channels": [0.5, 0.2, 0.41], "authoritative": True}}
    r = CC.compare(a, b)
    assert r["status"] == CC.COMPARABLE
    assert r["basis"] == "SOURCE values only"
    assert r["delta_e76"] >= 0


def test_lab_comparison_requires_identical_documented_assumptions():
    lab = {"raw": {"model": "LAB", "channels": [0.5, 20.0, -30.0],
                   "authoritative": True}}
    assert CC.can_compare(lab, lab, lab_assumption_a="D50",
                          lab_assumption_b="D65")["comparable"] is False


def test_a_colour_name_is_not_an_authoritative_identifier():
    r = CC.name_is_not_an_identifier("Pantone 3519 C")
    assert r["status"] == CC.UNAVAILABLE
    assert r["reason"] == CC.R_NAME


def test_the_real_ase_is_not_linked_to_historical_design_memory():
    h = CC.historical_link("Pantone_3519C.ase")
    assert h["linked_to_historical_design_memory"] is False
    assert h["retrievable"] is False
    assert h["automatically_usable"] is False
    assert any("historically used" in c for c in h["claims_not_made"])


# === queues ==================================================================
def test_queue_ids_are_identity_and_letters_are_only_labels():
    q = RV.build([], now=NOW)
    for qid, item in q["queues"].items():
        assert item["queue_id"] == qid
        assert item["display_label"] == RV.LABELS[qid]
        assert item["schema_version"] == RV.QUEUE_SCHEMA_VERSION
    # changing a label changes nothing about identity
    assert set(q["queues"]) == set(RV.QUEUE_IDS)


def test_queue_ids_are_globally_unique():
    assert len(set(RV.QUEUE_IDS)) == len(RV.QUEUE_IDS) == 14
    assert len({RV.LABELS[q] for q in RV.QUEUE_IDS}) == 14


def test_the_c3b4_queue_artifacts_remain_reproducible():
    """C3b4's letters meant something else. Its module is untouched and still works."""
    from tools.dip0c import review_c3b4
    old = review_c3b4.build([], now=NOW)
    assert set(old["queues"]) == {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J"}
    assert old["queues"]["B"]["title"] == "active canonical conflicts"
    # ...while C3d's B is a DIFFERENT queue entirely
    assert RV.TITLES["COMPOSITION_MISLABELLED_AS_MASTER"] != \
        old["queues"]["B"]["title"]


def test_canonical_and_palette_approvals_are_never_batch_approved():
    for qid in ("CANONICAL_MASTER_NOMINATION", "CANONICAL_CONFLICT",
                "PALETTE_APPROVAL_DUAL_CONTROL"):
        assert RV.BATCHABLE[qid] is False
    q = RV.build([], now=NOW)
    assert set(q["never_batch_approved"]) == {
        "CANONICAL_MASTER_NOMINATION", "CANONICAL_CONFLICT",
        "PALETTE_APPROVAL_DUAL_CONTROL"}


def test_palette_and_master_queues_do_not_merge_when_scopes_overlap():
    sc = S.scope("BBROSE")
    q = RV.build([_master("logo.ai", sc), _palette("p.ase", sc)], now=NOW)
    assert q["queues"]["CANONICAL_CONFLICT"]["count"] == 0   # different domains


def test_review_queues_are_deterministic():
    sc = S.scope("BBROSE")
    ev = [_master("logo.ai", sc), _palette("a.ase", sc),
          _palette("b.ase", sc, at=T2)]
    f = {"possible_masters": [{"asset": "z.ai"}, {"asset": "a.ai"}]}
    a = RV.build(ev, now=NOW, brand_findings=f)
    b = RV.build(list(reversed(ev)), now=NOW, brand_findings=f)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# === append-only, and the real ledger stays empty =============================
def test_palette_decisions_are_append_only():
    for et in L.PALETTE_EVENTS:
        assert et in L.EVENT_TYPES
        assert et in L.EVENT_ACTION
    for et in (L.PALETTE_DEPRECATED, L.PALETTE_SUPERSEDED,
               L.PALETTE_APPROVAL_REVOKED, L.PALETTE_RE_REVIEW_REQUIRED):
        assert et in L.CORRECTIVE_EVENTS      # a correction is a NEW event


def test_a_corrective_palette_event_must_name_what_it_supersedes():
    with pytest.raises(L.LedgerError, match="supersedes"):
        L.event("p.ase", event_type=L.PALETTE_APPROVAL_REVOKED, actor_id=LEGAL,
                actor_role=authz.LEGAL_REVIEWER, occurred_at=T,
                decision_reason="revoked")


def test_a_palette_decision_actually_persists_and_round_trips(tmp_path, monkeypatch):
    """The acceptance criterion says palette decisions can be RECORDED safely. Every
    other test builds events in memory and hands them to the projections — so the
    write path (append -> JSON -> load -> validate -> project) has never run for a
    palette event. An unexecuted path is not evidence.
    """
    from tools.dip0c import ledger_store as LS
    root = tmp_path / "decisions"
    monkeypatch.setattr(L, "LEDGER_ROOT", root)
    monkeypatch.setattr(L, "EVENTS_DIR", root / "events")
    monkeypatch.setattr(L, "EVIDENCE_DIR", root / "evidence")
    monkeypatch.setattr(L, "ASSERTIONS_DIR", root / "assertions")
    monkeypatch.setattr(L, "INDEX_PATH", root / "index.json")
    monkeypatch.setattr(LS, "KINDS", {
        "events": (root / "events", "event_id"),
        "evidence": (root / "evidence", "evidence_id"),
        "assertions": (root / "assertions", "assertion_id")})
    from tools.dip0c import compound as CP
    monkeypatch.setattr(CP, "COMPOUND_DIR", root / "compound")
    monkeypatch.setattr(C, "assert_output_safe", lambda p: p)
    LS.ensure_dirs()

    sc = S.scope("BBROSE", markets=["EU"], media=["DIGITAL"])
    evt = _palette("p.ase", sc)
    path = LS.append("events", evt)
    assert path.exists()

    # it survives the JSON round-trip, hash intact
    loaded = LS.load("events")
    assert len(loaded) == 1
    back = loaded[0]
    assert back["event_type"] == L.BRAND_PALETTE_APPROVED
    assert back["content_hash"] == L.content_hash(back)

    # the nested blocks survive: domain, palette audit, attestations
    can = back["canonical"]
    assert can["authority_domain"] == L.DOMAIN_BRAND_PALETTE
    assert can["palette"]["grants_permissions"] is False
    assert can["palette"]["parse_status"] == ase.TECHNICALLY_PARSED
    assert {a["actor_id"] for a in can["attestations"]} == {COLOR, LEGAL}

    # the validator — which now projects EVERY event through canonical_read — is clean
    report = LS.validate()
    assert report["valid"], report["findings"]
    assert report["counts"]["events"] == 1
    assert report["findings"]["overlapping_active_masters"] == []

    # and the persisted event projects correctly, in its own domain
    assert CR.canonical_for(loaded, sc, L.DOMAIN_BRAND_PALETTE)["asset"] == "p.ase"
    assert CR.canonical_for(loaded, sc, L.DOMAIN_BRAND_MASTER)["asset"] is None
    # ...and grants nothing
    eff = P.effective_permissions("p.ase", loaded, now=NOW)
    assert not any(r["value"] for r in eff["permissions"].values())

    # append-only. Re-appending byte-identical content is IDEMPOTENT (it is the same
    # fact, not a rewrite) — but the same id carrying DIFFERENT content is refused.
    # That is the property that matters: a decision may not be edited in place.
    assert LS.append("events", evt) == path
    assert len(LS.load("events")) == 1

    tampered = dict(evt)
    tampered["decision_reason"] = "something else entirely"
    with pytest.raises(L.LedgerError, match="IMMUTABLE"):
        LS.append("events", tampered)


def test_expiry_makes_effective_palette_permissions_false():
    expiry = "2026-10-01T00:00:00+00:00"
    after = "2026-10-02T00:00:00+00:00"
    grant = L.event(
        "p.ase", event_type=L.PERMISSION_GRANTED, actor_id=LEGAL,
        actor_role=authz.LEGAL_REVIEWER, occurred_at=T, decision_reason="r",
        review_expiry=expiry,
        permission=L.permission_block(
            "retrieval_allowed", previous_value=False, requested_value=True,
            purpose="p", approved_media=["DIGITAL"], validity_start=T,
            review_expiry=expiry))
    ev = [_palette("p.ase", S.scope("BBROSE", media=["DIGITAL"])), grant]
    before = P.effective_permissions("p.ase", ev, now=NOW, media="DIGITAL")
    assert before["permissions"]["retrieval_allowed"]["value"] is True
    lapsed = P.effective_permissions("p.ase", ev, now=after, media="DIGITAL")
    assert lapsed["permissions"]["retrieval_allowed"]["value"] is False
    assert lapsed["permissions"]["retrieval_allowed"]["status"] \
        == C.EFF_RE_REVIEW_REQUIRED
    # ...with NO expiry event present: the denial does not wait for an audit trail
    assert not any(e["event_type"] == L.PERMISSION_EXPIRED for e in ev)


def test_the_pilot_fabricates_no_real_palette_approval():
    p = run_c3d.build_pilot()
    assert p["real_ase_approval"]["allowed"] is False
    assert p["approval_grants_nothing"]["all_permissions_false"]
    assert p["dual_control"]["one_person_both_halves_allowed"] is False
    assert not any(a["reason"].startswith("NOT REFUSED") for a in p["refused"])
    for e in p["events"]:
        assert "TEST_ONLY" in e["asset"] or "TEST_ONLY" in e["actor_id"]


def test_the_real_ledger_stays_empty():
    from tools.dip0c import ledger_store as LS
    r = LS.validate()
    assert r["counts"]["events"] == 0
    assert r["counts"]["compound_events"] == 0
    assert r["valid"]
