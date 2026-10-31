"""WI2 — brand_gov.minimum_component_library.

The library is assembled from committed owner evidence. These tests pin
the contract, prove every refusal actually fires, and — the point of the
node — prove that provenance and permission cannot be omitted.
"""
import json
import os

import pytest
from django.conf import settings

from apps.pipeline.services import brand_component_library as b


@pytest.fixture(scope="module")
def lib():
    return b.build()


class TestContractIsPinned:
    def test_schema_and_minimum_set(self, lib):
        assert lib["schema_version"] == "brand_component_library/1.0"
        assert lib["minimum_set"] == ["LOGO", "MEDALLION",
                                      "REGISTERED_SYMBOL", "DIVIDER"]

    def test_the_minimum_set_is_exactly_what_is_built(self, lib):
        """MINIMUM means minimum. The expanded library is a separate
        tracker node, and a library that accretes components silently is
        how unlicensed artwork reaches production."""
        assert [c["id"] for c in lib["components"]] == list(b.MINIMUM_SET)
        assert lib["expanded_library_is_a_separate_node"] is True

    def test_origins_are_closed_and_none_of_them_means_unknown(self):
        assert b.ORIGINS == {"OWNER_CONFIRMED_VECTOR_EXTRACTION",
                             "GATE_A_VERIFIED_MEASUREMENT"}
        for bad in ("UNKNOWN", "GENERATED", "ASSUMED", "DEFAULT"):
            assert bad not in b.ORIGINS


class TestEveryComponentCarriesProvenanceAndPermission:
    """The node's own title, enforced rather than documented."""

    def test_every_component_has_a_complete_provenance(self, lib):
        for c in lib["components"]:
            for key in b.PROVENANCE_REQUIRED:
                assert c["provenance"].get(key), (c["id"], key)
            assert c["provenance"]["origin"] in b.ORIGINS

    def test_every_component_has_a_complete_permission(self, lib):
        for c in lib["components"]:
            for key in b.PERMISSION_REQUIRED:
                assert key in c["permission"], (c["id"], key)

    def test_permission_is_quoted_from_the_owner_record_not_restated(self,
                                                                    lib):
        """Hard-coding the scope would let this module and the owner's
        record drift apart silently, and the module would win."""
        rec = json.load(open(os.path.join(settings.BASE_DIR, b.LOGO_RECORD)))
        oc = rec["owner_confirmation"]
        assert lib["permission"]["scope"] == oc["scope"]
        assert lib["permission"]["owner_codes"] == oc["codes"]
        assert lib["permission"]["confirmed_by"] == oc["confirmed_by"]

    def test_third_party_assets_are_not_authorized(self, lib):
        assert lib["permission"]["third_party_authorized"] is False

    def test_a_component_cannot_be_built_without_provenance(self):
        with pytest.raises(b.BrandLibraryRefusal) as exc:
            b._component("X", "rule", {}, {"scope": "s",
                                           "third_party_authorized": False,
                                           "owner_codes": []})
        assert any(f.startswith(b.BRAND_LIB_PROVENANCE_INCOMPLETE)
                   for f in exc.value.findings)

    def test_a_component_cannot_be_built_without_permission(self):
        with pytest.raises(b.BrandLibraryRefusal) as exc:
            b._component("X", "rule",
                         {"origin": "GATE_A_VERIFIED_MEASUREMENT",
                          "source": {"a": 1}, "confirmation_state": "S"}, {})
        assert any(f.startswith(b.BRAND_LIB_PERMISSION_INCOMPLETE)
                   for f in exc.value.findings)

    def test_an_origin_outside_the_closed_set_refuses(self):
        with pytest.raises(b.BrandLibraryRefusal) as exc:
            b._component("X", "rule",
                         {"origin": "GENERATED", "source": {"a": 1},
                          "confirmation_state": "S"},
                         {"scope": "s", "third_party_authorized": False,
                          "owner_codes": []})
        assert any(f.startswith(b.BRAND_LIB_ORIGIN_NOT_RECOGNISED)
                   for f in exc.value.findings)


class TestTheTwoProvenanceClassesDoNotBlur:
    def test_the_three_marks_are_owner_confirmed_extractions(self, lib):
        for cid in ("LOGO", "MEDALLION", "REGISTERED_SYMBOL"):
            c = b.component(cid)
            assert c["provenance"]["origin"] == \
                "OWNER_CONFIRMED_VECTOR_EXTRACTION"
            assert c["provenance"]["confirmation_state"] == "OWNER_CONFIRMED"

    def test_the_divider_is_a_measurement_and_says_so(self, lib):
        """The divider is NOT extracted brand artwork. Recording it under
        the extraction origin would claim an authority it does not
        have."""
        d = b.component("DIVIDER")
        assert d["provenance"]["origin"] == "GATE_A_VERIFIED_MEASUREMENT"
        assert d["asset"] is None
        assert d["geometry"]["stroke_width_pt"] == 0.362384

    def test_only_the_divider_lacks_an_asset(self, lib):
        assert [c["id"] for c in lib["components"] if c["asset"] is None] \
            == ["DIVIDER"]


class TestTheApprovedArtworkIsHashVerified:
    def test_the_asset_matches_the_hash_the_owner_confirmed(self, lib):
        rec = json.load(open(os.path.join(settings.BASE_DIR, b.LOGO_RECORD)))
        asset = b.component("LOGO")["asset"]
        assert asset["path"] == rec["canonical_ai"]
        assert asset["sha256_16"] == rec["canonical_ai_sha256"]
        assert os.path.exists(os.path.join(settings.BASE_DIR, asset["path"]))

    def test_a_changed_asset_refuses(self):
        """NEGATIVE CONTROL. A component that cannot prove it is still
        the artwork that was approved is not a usable brand component."""
        with pytest.raises(b.BrandLibraryRefusal) as exc:
            b._verified_asset(
                "docs/visual_quality/vq2/brand/bbrose_logo_approved.ai",
                "0000000000000000", "LOGO")
        assert exc.value.findings[0].startswith(
            b.BRAND_LIB_ASSET_HASH_MISMATCH)

    def test_a_missing_asset_refuses(self):
        with pytest.raises(b.BrandLibraryRefusal) as exc:
            b._verified_asset("docs/nope/absent.ai", "x", "LOGO")
        assert exc.value.findings[0].startswith(b.BRAND_LIB_ASSET_MISSING)

    def test_a_missing_source_record_refuses(self):
        with pytest.raises(b.BrandLibraryRefusal) as exc:
            b._load("docs/visual_quality/vq2/does_not_exist.json")
        assert exc.value.findings[0].startswith(
            b.BRAND_LIB_SOURCE_RECORD_MISSING)


class TestAnExtractionMustStillBeAnExtraction:
    def test_the_seven_negatives_hold_on_the_committed_record(self):
        rec = json.load(open(os.path.join(settings.BASE_DIR, b.LOGO_RECORD)))
        for key in b.EXTRACTION_NEGATIVES:
            assert rec.get(key) is False, key
        assert rec["is_extraction_not_reconstruction"] is True

    @pytest.mark.parametrize("flipped", b.EXTRACTION_NEGATIVES)
    def test_flipping_any_negative_refuses(self, flipped):
        """NEGATIVE CONTROL, one per negative. If the mark was traced or
        redrawn or had a font substituted, it is our drawing of the
        owner's mark and the confirmation no longer covers it."""
        rec = json.load(open(os.path.join(settings.BASE_DIR, b.LOGO_RECORD)))
        rec[flipped] = True
        with pytest.raises(b.BrandLibraryRefusal) as exc:
            b._assert_extraction_is_an_extraction(rec)
        assert flipped in exc.value.findings[0]

    def test_a_reconstruction_refuses(self):
        rec = json.load(open(os.path.join(settings.BASE_DIR, b.LOGO_RECORD)))
        rec["is_extraction_not_reconstruction"] = False
        with pytest.raises(b.BrandLibraryRefusal):
            b._assert_extraction_is_an_extraction(rec)


class TestInkAuthorityTravelsWithTheMark:
    def test_the_guideline_cyan_is_not_this_product_s_ink(self, lib):
        """The brand guideline publishes the logo in CYAN and this
        product does not use it. Handing out the mark without its
        authorized ink is how the wrong colour ships."""
        ia = lib["ink_authority"]
        assert ia["guideline_colour_used"] is False
        assert "cyan" in ia["guideline_source_colour"].lower()
        assert ia["selected_product_ink"] == "#502525"
        assert ia["logo_geometry_altered"] is False

    def test_the_divider_ink_is_the_live_one_not_the_superseded_a2_value(
            self, lib):
        """A2 used four near-but-not-equal browns; the divider's A2 ink
        #66433A is SUPERSEDED. Reading the stale key would have shipped
        a colour the owner replaced."""
        d = b.component("DIVIDER")
        assert d["geometry"]["ink_hex"] == lib["ink_authority"][
            "selected_product_ink"]
        assert d["geometry"]["ink_hex"] != "#66433A"
        assert d["geometry"]["ink_is_shared_not_component_specific"] is True

    def test_the_prohibited_treatments_are_carried_not_summarised(self, lib):
        prohibited = lib["ink_authority"]["prohibited_absent"]
        for key in ("bright_cyan", "gradient", "metallic_simulation",
                    "transparency", "glow", "material_effect"):
            assert prohibited[key] is True, key


class TestLookupIsFailClosed:
    def test_an_unknown_component_refuses_rather_than_guessing(self):
        """There is no default and no nearest match — guessing which
        brand component the caller meant is how the wrong mark gets
        emitted."""
        for junk in ("logo", "ROSE", "", "MEDALLION_2", "DIVIDER "):
            with pytest.raises(b.BrandLibraryRefusal) as exc:
                b.component(junk)
            assert exc.value.findings[0].startswith(
                b.BRAND_LIB_COMPONENT_UNKNOWN)

    def test_every_minimum_component_resolves(self):
        for cid in b.MINIMUM_SET:
            assert b.component(cid)["id"] == cid


class TestPurity:
    def test_the_library_reaches_no_provider_and_no_database(self):
        """A brand component library that can hit the ORM or a provider
        is a library whose answers depend on runtime state."""
        src = open(os.path.join(settings.BASE_DIR, "apps", "pipeline",
                                "services",
                                "brand_component_library.py")).read()
        for banned in ("anthropic", "openai", "requests", "objects.",
                       "models import", "urllib"):
            assert banned not in src, banned
