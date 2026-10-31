"""DIP-0C3c — ASE parser, palette records, naming and rights."""
from __future__ import annotations

import struct

import pytest

from tools.dip0c import ase
from tools.dip0c import config as C
from tools.dip0c import palette as PAL
from tools.dip0c import palette_rights as PR
from tools.dip0c import run_c3c

# --- fixture builders ---------------------------------------------------------
MODELS = {"RGB": (b"RGB ", 3), "CMYK": (b"CMYK", 4), "LAB": (b"LAB ", 3),
          "GRAY": (b"GRAY", 1)}


def color_body(name, model="RGB", vals=(0.1, 0.2, 0.3), ctype=0,
               *, with_length=True):
    tok, _ = MODELS[model]
    n = name + "\x00"
    body = b""
    if with_length:
        body += struct.pack(">H", len(n))
    body += n.encode("utf-16-be") + tok
    body += struct.pack(">" + "f" * len(vals), *vals)
    body += struct.pack(">H", ctype)
    return body


def block(btype, body):
    return struct.pack(">HI", btype, len(body)) + body


def ase_file(*blocks, version=(1, 0), count=None, trailing=b""):
    n = len(blocks) if count is None else count
    return (b"ASEF" + struct.pack(">HH", *version) + struct.pack(">I", n)
            + b"".join(blocks) + trailing)


def group_body(name, with_length=True):
    n = name + "\x00"
    b = struct.pack(">H", len(n)) if with_length else b""
    return b + n.encode("utf-16-be")


# === valid swatches, every model ==============================================
@pytest.mark.parametrize("model,vals,ctype", [
    ("RGB", (0.1, 0.2, 0.3), 0),
    ("CMYK", (0.0, 1.0, 0.5, 0.1), 2),
    ("LAB", (0.5, 20.0, -30.0), 1),
    ("GRAY", (0.25,), 0),
])
def test_a_valid_swatch_parses_in_every_model(model, vals, ctype):
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR,
                                 color_body("S", model, vals, ctype))))
    assert d["parse_status"] == ase.TECHNICALLY_PARSED
    assert d["capability"] == ase.CAP_DIRECT
    s = d["swatches"][0]
    assert s["model"] == model
    assert s["channels"] == pytest.approx(list(vals), abs=1e-6)
    assert s["color_type"] == ase.COLOR_TYPES[ctype]
    assert s["layout"] == ase.LAYOUT_STANDARD
    assert s["fallback_used"] is False


@pytest.mark.parametrize("ctype,name", [(0, "GLOBAL"), (1, "SPOT"), (2, "NORMAL")])
def test_every_color_type_is_recognised(ctype, name):
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR,
                                 color_body("S", ctype=ctype))))
    assert d["swatches"][0]["color_type"] == name


def test_utf16be_names_including_non_ascii():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, color_body("Rosé — Ø 3519"))))
    assert d["swatches"][0]["name"] == "Rosé — Ø 3519"


# === groups ===================================================================
def test_group_start_and_end():
    d = ase.parse(ase_file(
        block(ase.BLOCK_GROUP_START, group_body("Brand")),
        block(ase.BLOCK_COLOR, color_body("Red")),
        block(ase.BLOCK_GROUP_END, b"")))
    assert d["parse_status"] == ase.TECHNICALLY_PARSED
    assert [g["name"] for g in d["groups"]] == ["Brand"]
    assert d["swatches"][0]["group"] == "Brand"
    assert d["groups"][0]["swatch_names"] == ["Red"]


def test_multiple_groups():
    d = ase.parse(ase_file(
        block(ase.BLOCK_GROUP_START, group_body("A")),
        block(ase.BLOCK_COLOR, color_body("a1")),
        block(ase.BLOCK_GROUP_END, b""),
        block(ase.BLOCK_GROUP_START, group_body("B")),
        block(ase.BLOCK_COLOR, color_body("b1")),
        block(ase.BLOCK_GROUP_END, b"")))
    assert [g["name"] for g in d["groups"]] == ["A", "B"]
    assert d["parse_status"] == ase.TECHNICALLY_PARSED


def test_unbalanced_groups_are_flagged():
    d = ase.parse(ase_file(
        block(ase.BLOCK_GROUP_START, group_body("A")),
        block(ase.BLOCK_COLOR, color_body("a1"))))
    assert ase.W_GROUP_UNBALANCED in d["warnings"]
    assert d["parse_status"] == ase.PARTIAL_PARSE


# === the malformed cases: fail closed, never guess ============================
def test_truncated_header():
    d = ase.parse(b"ASEF\x00\x01")
    assert d["parse_status"] == ase.PARSE_FAILED
    assert ase.W_TRUNCATED_HEADER in d["warnings"]


def test_bad_signature():
    d = ase.parse(b"NOPE" + b"\x00" * 20)
    assert d["parse_status"] == ase.PARSE_FAILED
    assert "BAD_SIGNATURE" in d["warnings"]


def test_truncated_block():
    full = ase_file(block(ase.BLOCK_COLOR, color_body("Red")))
    d = ase.parse(full[:-6])                       # chop the tail off the body
    assert d["parse_status"] == ase.PARTIAL_PARSE
    assert ase.W_TRUNCATED_BLOCK in d["warnings"]


def test_an_invalid_block_length_does_not_cross_the_boundary():
    """The block says it holds a CMYK swatch but declares too few bytes."""
    body = color_body("Red", "CMYK", (0.1, 0.2, 0.3, 0.4))
    short = body[:-6]                              # channels no longer fit
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, short)))
    assert d["parse_status"] == ase.PARSE_FAILED
    assert d["swatches"] == []
    assert "cross" in d["blocks"][0]["error"] or "fit" in d["blocks"][0]["error"]


def test_malformed_utf16_is_refused():
    # a name length that is not NUL-terminated where it claims to end
    body = struct.pack(">H", 3) + "AB".encode("utf-16-be") + b"\x00\x41"
    body += b"RGB " + struct.pack(">fff", 0, 0, 0) + struct.pack(">H", 0)
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, body)))
    assert d["parse_status"] == ase.PARSE_FAILED
    assert d["swatches"] == []


def test_an_unsupported_color_model_is_refused():
    body = struct.pack(">H", 2) + "A\x00".encode("utf-16-be") + b"XYZ "
    body += struct.pack(">fff", 0, 0, 0) + struct.pack(">H", 0)
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, body)))
    assert d["parse_status"] == ase.PARSE_FAILED


def test_an_invalid_color_type_is_refused():
    body = color_body("Red")[:-2] + struct.pack(">H", 99)
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, body)))
    assert d["parse_status"] == ase.PARSE_FAILED


def test_trailing_bytes_are_reported_not_ignored():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, color_body("Red")),
                           trailing=b"\xde\xad\xbe\xef"))
    assert d["trailing_bytes"] == 4
    assert ase.W_TRAILING_BYTES in d["warnings"]
    assert d["parse_status"] == ase.PARTIAL_PARSE


def test_a_declared_block_count_mismatch_is_reported():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, color_body("Red")), count=7))
    assert ase.W_BLOCK_COUNT_MISMATCH in d["warnings"]
    assert d["parse_status"] == ase.PARTIAL_PARSE


# === unknown blocks are PRESERVED, not skipped ================================
def test_an_unknown_block_is_preserved_not_interpreted():
    d = ase.parse(ase_file(block(0x7777, b"\x01\x02\x03\x04"),
                           block(ase.BLOCK_COLOR, color_body("Red"))))
    assert d["parse_status"] == ase.UNSUPPORTED_BLOCK
    assert ase.W_UNKNOWN_BLOCK in d["warnings"]
    unk = d["blocks"][0]
    assert unk["type"] == "0x7777"
    assert unk["preserved_body_sha256"]            # the bytes are kept
    assert "will not guess" in unk["note"]
    assert len(d["swatches"]) == 1                 # the rest still parses


# === THE LAYOUT PROTOCOL =====================================================
def test_the_documented_layout_is_used_when_it_works():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR,
                                 color_body("Red", with_length=True))))
    assert d["layouts_seen"] == [ase.LAYOUT_STANDARD]
    assert d["fallback_used"] is False
    assert d["parse_status"] == ase.TECHNICALLY_PARSED


def test_the_fallback_is_used_only_when_the_standard_layout_is_impossible():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR,
                                 color_body("Red", with_length=False))))
    assert d["layouts_seen"] == [ase.LAYOUT_NON_STANDARD]
    assert d["fallback_used"] is True
    assert ase.W_NAME_LENGTH_ABSENT in d["warnings"]
    s = d["swatches"][0]
    assert s["name"] == "Red"
    assert s["unexplained_bytes"] == 0             # consumed the body EXACTLY
    assert "PROVABLY impossible" in s["standard_failure_reason"]


def test_a_file_needing_the_fallback_can_never_be_technically_parsed():
    """Needing a fallback is itself a finding."""
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR,
                                 color_body("Red", with_length=False))))
    assert d["parse_status"] == ase.PARTIAL_PARSE
    assert d["parse_status"] != ase.TECHNICALLY_PARSED
    assert d["capability"] == ase.CAP_REQUIRES_HUMAN


def test_a_fallback_that_leaves_unexplained_bytes_is_refused():
    body = color_body("Red", with_length=False) + b"\x00\x00\x00\x00"
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, body)))
    assert d["parse_status"] == ase.PARSE_FAILED
    assert d["swatches"] == []


def test_when_neither_layout_parses_the_answer_is_parse_failed():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, b"\x01\x02\x03")))
    assert d["parse_status"] == ase.PARSE_FAILED
    assert d["capability"] == ase.CAP_REQUIRES_HUMAN
    assert d["swatches"] == []


def ambiguous_body():
    """A block with TWO valid fallback readings, each consuming it exactly:

      split A (the first NUL) -> name "A",  model CMYK (4 channels) -> ends exactly
      split B (a later NUL)   -> longer name, model GRAY (1 channel) -> ends exactly

    The trick is that one channel float (0.5 = 0x3F000000) ends in two NUL bytes, and
    the next float's bytes happen to spell a valid model token. A parser that simply
    took the first NUL would silently pick A and never know B existed.
    """
    body = "A".encode("utf-16-be") + b"\x00\x00"
    body += (b"CMYK" + struct.pack(">f", 0.25) + b"\x3f\x00\x00\x00"
             + b"GRAY" + struct.pack(">f", 0.75) + struct.pack(">H", 0))
    return body


def test_the_parser_never_chooses_between_two_valid_readings():
    """If more than one fallback reading consumes the block exactly, REFUSE.
    Picking the first one that works is exactly the guessing this parser forbids."""
    body = ambiguous_body()
    assert ase._ambiguous(body) is True

    r = ase.parse_color_block(body)
    assert r["ok"] is False
    assert ase.W_AMBIGUOUS_LAYOUT in r["warnings"]
    assert "will not choose" in r["why"]

    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, body)))
    assert d["parse_status"] == ase.PARSE_FAILED
    assert d["capability"] == ase.CAP_REQUIRES_HUMAN
    assert d["swatches"] == []

    # ...while the real file's shape has exactly ONE valid reading
    assert ase._ambiguous(color_body("Red", with_length=False)) is False


# === determinism + the source is never touched ===============================
def test_the_parse_is_deterministic():
    data = ase_file(block(ase.BLOCK_GROUP_START, group_body("G")),
                    block(ase.BLOCK_COLOR, color_body("Red")),
                    block(ase.BLOCK_GROUP_END, b""))
    assert ase.parse(data) == ase.parse(data)


def test_serialization_is_deterministic_and_round_trips():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, color_body("Red"))))
    a, b = ase.serialize(d), ase.serialize(d)
    assert a == b
    assert ase.parse(a)["swatches"][0]["channels"] == \
        pytest.approx(d["swatches"][0]["channels"])


def test_the_parser_never_modifies_the_source(tmp_path):
    p = tmp_path / "x.ase"
    data = ase_file(block(ase.BLOCK_COLOR, color_body("Red")))
    p.write_bytes(data)
    before = p.read_bytes()
    ase.parse_file(p)
    assert p.read_bytes() == before


# === raw vs derivative =======================================================
def test_raw_values_are_authoritative_and_previews_are_derivative():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR,
                                 color_body("C", "CMYK", (0.0, 1.0, 0.5, 0.1), 2))))
    rec = PAL.swatch_record(d["swatches"][0])
    assert rec["raw"]["authoritative"] is True
    assert rec["raw"]["model"] == "CMYK"
    assert rec["raw"]["channels"] == pytest.approx([0.0, 1.0, 0.5, 0.1])
    n = rec["normalized"]
    assert n["conversion_method"] == PAL.CONV_NAIVE_CMYK
    assert PAL.W_NO_ICC in n["warnings"]
    assert PAL.W_PREVIEW_ONLY in n["warnings"]
    assert n["confidence"] <= PAL.CONF_PREVIEW
    assert "never replace the source" in n["note"]


def test_no_print_accurate_rgb_is_claimed_from_cmyk_without_an_icc_profile():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR,
                                 color_body("C", "CMYK", (0.2, 0.2, 0.2, 0.2)))))
    n = PAL.normalize(d["swatches"][0])
    assert PAL.W_NO_ICC in n["warnings"]
    assert n["conversion_method"] == PAL.CONV_NAIVE_CMYK


def test_lab_records_its_illuminant_assumption_and_is_not_silently_converted():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR,
                                 color_body("L", "LAB", (0.5, 20.0, -30.0)))))
    n = PAL.normalize(d["swatches"][0])
    assert PAL.W_LAB_ILLUMINANT_ASSUMED in n["warnings"]
    assert n["lab"] == [50.0, 20.0, -30.0]
    assert n["srgb_preview"] is None        # no silently-clipped preview


def test_a_spot_identity_is_never_replaced_by_its_preview():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR,
                                 color_body("Spot", "RGB", (0.5, 0.1, 0.2), 1))))
    rec = PAL.swatch_record(d["swatches"][0])
    assert rec["raw"]["color_type"] == "SPOT"
    assert PAL.W_SPOT_ALTERNATE in rec["normalized"]["warnings"]
    assert rec["normalized"]["confidence"] <= PAL.CONF_PREVIEW


def test_out_of_range_channels_are_flagged_not_silently_clipped_away():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR,
                                 color_body("X", "RGB", (1.5, -0.2, 0.5)))))
    rec = PAL.swatch_record(d["swatches"][0])
    assert rec["raw"]["channels"] == pytest.approx([1.5, -0.2, 0.5])   # RAW kept
    assert rec["normalized"]["clipping_warning"] is True


# === naming, ownership, permissions ==========================================
def test_a_machine_may_never_approve_a_palette_or_a_right():
    for state in PR.HUMAN_ONLY:
        with pytest.raises(C.HumanOnlyStateViolation):
            PR.machine_palette_state(state)
    for state in PR.MACHINE_ALLOWED:
        assert PR.machine_palette_state(state) == state


def test_pantone_naming_is_evidence_not_a_definition():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR,
                                 color_body("Pantone 3519 C", "RGB",
                                            (0.5, 0.2, 0.4), 0))))
    d["source"] = "materials/x/Pantone_3519C.ase"
    n = PR.naming_evidence(d)
    assert n["detected_naming_systems"] == ["PANTONE"]
    assert n["third_party_naming_present"] is True
    assert n["contains_spot_identity"] is False
    assert n["authoritative_definition_present"] is False
    assert any("only in a NAME STRING" in f for f in n["findings"])


def test_the_filename_proves_nothing():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, color_body("swatch"))))
    d["source"] = "materials/BBROSE OFFICIAL/BBROSE_BRAND_PALETTE.ase"
    n = PR.naming_evidence(d)
    r = PR.rights_record(d, n)
    assert r["ownership_status"] == PR.OWNERSHIP_UNCONFIRMED
    assert r["brand_association"] == PR.REQUIRES_HUMAN
    assert not any(r["permissions"].values())


def test_every_permission_defaults_to_false():
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, color_body("x"))))
    d["source"] = "materials/x.ase"
    r = PR.rights_record(d, PR.naming_evidence(d))
    assert set(r["permissions"]) >= {"retrieval_allowed", "automatic_use_allowed",
                                     "production_use_allowed"}
    assert not any(r["permissions"].values())
    assert r["human_review_required"] is True


def test_a_perfectly_parsed_palette_is_still_unusable():
    """Technical and rights are separate axes; they never collapse into one."""
    d = ase.parse(ase_file(block(ase.BLOCK_COLOR, color_body("Red"))))
    d["source"] = "materials/x.ase"
    assert d["parse_status"] == ase.TECHNICALLY_PARSED       # technically perfect
    r = PR.rights_record(d, PR.naming_evidence(d))
    assert not any(r["permissions"].values())                # ...and still unusable


def test_the_approval_contract_is_defined_but_unanswered():
    cl = PR.blank_approval()
    assert len(cl) == len(PR.APPROVAL_CHECKLIST)
    assert all(v["result"] is None for v in cl.values())      # None is NOT a pass


# === the real file — pinned only on what the parser PROVED ===================
def test_the_real_ase_matches_the_recorded_policy():
    a = run_c3c.audit()
    p = a["palette"]["palette"]
    assert p["signature"] == "ASEF"
    assert p["version"] == [1, 0]
    assert p["declared_block_count"] == 1
    assert p["group_count"] == 0
    assert p["swatch_count"] == 1
    # the policy the business set for this file
    assert p["parse_status"] == ase.PARTIAL_PARSE
    assert p["capability"] == ase.CAP_REQUIRES_HUMAN
    assert p["layouts_seen"] == [ase.LAYOUT_NON_STANDARD]
    assert ase.W_NAME_LENGTH_ABSENT in p["parser_warnings"]
    assert p["fallback_used"] is True
    assert p["parse_status"] != ase.TECHNICALLY_PARSED

    r = a["rights"]
    assert r["ownership_status"] == PR.OWNERSHIP_UNCONFIRMED
    assert r["license_status"] == PR.LICENSE_UNVERIFIED
    assert r["brand_association"] == PR.REQUIRES_HUMAN
    assert r["permissions"]["retrieval_allowed"] is False
    assert r["permissions"]["automatic_use_allowed"] is False
    assert r["permissions"]["production_use_allowed"] is False


def test_the_real_ase_carries_no_authoritative_pantone_definition():
    """The bytes, not the filename: GLOBAL RGB, no spot, no CMYK, no Lab, no ICC."""
    a = run_c3c.audit()
    s = a["palette"]["swatches"][0]["raw"]
    assert s["model"] == "RGB"
    assert s["color_type"] == "GLOBAL"
    assert a["naming"]["contains_spot_identity"] is False
    assert a["naming"]["authoritative_definition_present"] is False
    assert a["naming"]["detected_naming_systems"] == ["PANTONE"]


def test_the_review_item_leaves_every_human_field_blank():
    item = run_c3c.review_item(run_c3c.audit())
    h = item["human"]
    assert h["ownership_confirmation"] is None
    assert h["brand_association"] is None
    assert h["palette_approval"] is None
    assert h["approved_brands"] == [] and h["approved_markets"] == []
    assert h["review_expiry"] is None
    assert item["batch_review_allowed"] is False
    assert all(v["result"] is None for v in item["approval_contract"].values())
