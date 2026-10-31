"""The owner-grant channel for materials — §BH36(a) built at §BH37(1), in the
§BH26(a) shape of ``container_font_owner_grant``.

A grant is transcribed owner data: ONE ROW PER FILE keyed by the file's sha256,
scoped to the pack the governing terms text sits beside (§BH37(4): a byte-identical
copy in another folder is not raised — the evidence is the text beside THIS pack),
pinned to the governing terms text by path AND sha256. The
channel is applied at read time, AFTER ``build_tier_record`` and never inside
it; the evidence file is re-hashed on EVERY application, so a text that moved or
changed voids its grant and the row stays at REFERENCE — fail-closed, never an
error-shaped pass. A sha256 no grant names is left exactly as the machine wrote
it. Where the governing text requires a credit, the grant carries it VERBATIM in
``condition`` — the wiring front enforces it on outputs.

§BH37(1) lands the channel with NO rows; §BH37(4) lands the rows as a
single-use authority, spent on that landing.
"""
from __future__ import annotations

from pathlib import Path

from apps.ire.materials_authority import (
    TIER_PRODUCTION,
    TIER_REFERENCE,
    TIER_SOURCE_OWNER_GRANT,
    machine_writable_tier,
    sha256_of_file,
)

SCHEMA = "materials_owner_grant/1.0"

#: the repository root — the grants pin evidence by a repository-relative path
REPO_ROOT = Path(__file__).resolve().parents[3]

_REQUIRED_FIELDS = ("granted_by", "granted_at", "terms_class",
                    "evidence_path", "evidence_sha256", "file_sha256s")

#: §BH37(4): a grant's SCOPE — the materials-relative paths the governing text sits beside. A row is raised only when
#: its sha256 is named AND its path is in scope; a byte-identical copy elsewhere (ADOBE STOCK, REFERENCE by §BH36(b))
#: keeps the machine tier. A grant without ``paths`` is unscoped by sha256 alone (the §BH37(1) shape).
SCOPE_FIELD = "paths"

#: §BH37(4) fills this tuple — one row per granted file, keyed by sha256.
#: §BH37(4) — the owner's grants for the PERMISSIVE and ATTRIBUTION-REQUIRED packs of the §BH36 table, ONE ROW PER FILE
#: keyed by sha256; the governing text pinned by path AND sha256 (re-measured from the bytes when this tuple was
#: generated; re-hashed on every application); the credit carried verbatim. Single-use authority, spent on the
#: landing of the commit that carried the rows. §BH38 RIDING RULING (2026-09-07): the terms and read-me texts of the
#: granted packs are not granted files — evidence governs assets, it is not an asset — so no LICENSE_EVIDENCE row is
#: named here; the evidence PINS are unchanged; two grants that then named no file (baloo, codex) are gone.
#: §BH39(c) (2026-09-08): the owner's OWN-WORK packs granted by OWNER DECLARATION — the evidence is the tracked declaration
#: record (path + sha256, re-hashed on every application) that quotes the §BH39 register line and carries each pack's sha256 set.
#: §BH39(d): the evidence file itself is never a granted row — the Coolvetica EULA returned to REFERENCE.
MATERIAL_GRANTS: tuple = (
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-08",
        "terms_class": "OWNER_DECLARATION",
        # own_work_declaration_bh39.json (§BH39(c)) beside the pack — §BH36 class table, ruled at §BH37
        "evidence_path": "docs/design_intelligence/dip0a/own_work_declaration_bh39.json",
        "evidence_sha256": "06d9cfcc324935898d0eaea4f0b7fbf0b901b231d3847cf536523cf84598943a",
        "condition": "",
        "file_sha256s": (
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/BATH OIL/bath oil lorenza.ai
            "faa0b94b5e84c0dfeef7fd9b34bc0d274bda0fd62ccd9da84914f215154dff5d",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/BATH OIL/bath oil lorenza.jpg
            "99a71fbcf914ad90ee630459d3f5b3bcd1e45bcc3162a8923f934c6692b9a8cf",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/FACE OILE/FACE OIL LORENZA .ai
            "adde2da3b557a5586b98bfc442b0d88ff388e1bc6428484519def469dd49ac67",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/FACE OILE/FACE OIL LORENZA .jpg1.jpg
            "d814ee6b3c716e94fd609f750c63a143561d2c1e2867cf05f859476fbee11425",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/FACE WASH FOAM/FACE WASH FOAM.ai
            "a0f7857cf8fafcae334c51f8d3707ee6a2e4bc728ae5fec5c66e38068e791796",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/FACE WASH FOAM/FACE WASH FOAM111.jpg
            "9b808535de98ddc3fc91eea791dfe6a87a3c3adcaef54077ef71aee4a5f5adf6",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/Hair conditioner/1.psd
            "bbbd75d033415b45857b837ac1639585deb73c46ad0db38e946698a9b115513f",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/Hair conditioner/Hair conditioner lorenza.jpg
            "fd96a2c5f415817047fc7fe360e2e434b0fa66fe208aa3a1f1634f51f7afa65a",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/Hair conditioner/Hair conditioner.ai
            "c4370cd01f9628e5ac2e9694b6357b991f47d7192c6c5c6d193da3b17820103b",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/Hair conditioner/Hair conditioner.jpg222.jpg
            "adf4763782ad7732db86c3781aaeb1f7a958c01d09aadb8ba785df1637f4c7c7",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/LIP PALM LORENZA0/LIP PALM  LORENZA.jpg
            "c7ae670564ff825a33cb9ca6e7a5e1ce1f829a6c2c2da26f4a94dbec2aeda704",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/LIP PALM LORENZA0/LIP PALM LORENZA0.ai
            "3fc86cdbe56a31dc3a81d74981ae6d03818ada955818cdbdeba0fc45c80a87e4",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/NIGHT DAY CREAM 1/NIGHT & NIGHT CREAM LORENZA.ai
            "333b75fa0b123f1d7cd2e94419b7627e037134ecc85705f47a76cd6ee362854f",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/NIGHT DAY CREAM 1/NIGHT & NIGHT CREAM LORENZA.jpg
            "115118495615c8810a84aca541838c6f31fb4f8df94a6dafb3aa9ad2d9ae2b7e",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/SUN SCREEN LORENZA/SUN SCREEN LORENZA.ai
            "dceea785ca59447456ccd940a12cc03ae0fe7c1f239dd10590cf5015ce8acc1d",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/SUN SCREEN LORENZA/SUN SCREEN LORENZA.jpg
            "de04e44c9456278de6e58ec4ed0b8a44c5bf6dd774c0d074e64a61a79c2d6305",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/body wash/body wash lorenza.ai
            "31101bfb3df8e3cd31139d40a50a035eec97d0092c9f9b36d191b96cb37de16b",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/body wash/body wash lorenza.jpg1111.jpg
            "24ffe5aed7ddfb319447f9190ad60e93c771da259939d9fdd96370dd275713fb",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day and night 2 lorenza/day and night cream 2 lorenza.ai
            "d1d64864b3d01827a68766586d92f172ace6f2e3c8250ce0199b607a12876c51",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day and night 2 lorenza/day and night cream 2 lorenza.jpg
            "14e09bd21af672fe7dc145a8a9c017d0d6eb7ee6d9475e50103ee8c551418d61",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day cream 2 lorenza/day cream 2.jpg
            "4ee21599a8ab8df6f8b10216f35e3b7e152d4691fa44c4e5563934eb34186285",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day cream 2 lorenza/كريم نهاري لورنزا.ai
            "af7acbd509ee14d143abef5b853bbada76df4e9924064dbb3a1bfdd892bcdc20",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day cream lorenza/day cream lorenza.ai
            "234dad02264b4b53eb189cf01a125e8d7cf818823222882c380240b5d39bc442",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day cream lorenza/day cream lorenza.jpg
            "69812e96d5e1d488ac5be5150bcf00848ae7bf18c89e5f806446c753e5c88495",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face serum lorenza/face serum lorenza..ai
            "9bcf748d3f267928e5cb288917393b7b1809202235edcd0a932e9f7153f1ab34",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face serum lorenza/face serum lorenza..jpg
            "88f977ff528d8e11d6e9d8d7fcd6cf2f3e4ada382ece2f07cfb052c99a2c1ac8",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face wach lorenza3/FACE WACH 1.ai
            "72bc81a66bab59ce1a1a7411af9c214aca9a684339306ac2374f28fb6a3d6608",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face wach lorenza3/FACE WACH 1.jpglorenza 3.jpg
            "ff7e80033bf4c1b7cfc1d07607e2ea372f2bbee6c590fabe39e8f1ad3384f375",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face wash tube/face wash tube.ai
            "9cbcd49e497deedb239ea6268329dea0aad0a7cc84726e8f595b9bf36eb9a74b",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face wash tube/face wash tube.jpg
            "e366a2bed761221eb4d221121b50f729e7da18021f91d56ceadc4dc17047acb0",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face wash tube/غسول وجه جل.psd
            "a2daa4b8153b814a457874c4128ec6d1b6b7d6e029449b3ab4fea0ecefa4b3d4",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/hair oil lorenza/hair oil.ai
            "6f074ee5f21e91f66056adac689aefc033209f01216f8fc87de81da09d1c3293",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/hair oil lorenza/hair oil.jpg
            "2a4d4301bbdc7b1b0ce7eae292bd1a3f58175d7f4d1279778bf2932b5c6d40cc",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/hair serum lorenza/hair serum lorenza.ai
            "2d04dab63fe97a14c6a623584374c4661f59fbbfb4cf24adee9e9e435010f38c",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/hair serum lorenza/hair serum lorenza.jpg111.jpg
            "f0c697c2736c4a374098e0619788c7598aec0cfeeaa906db0f235d4e2e07478e",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/SCRUB LORENZA.ai
            "c4f0b05854f7bb6f3025dc265bc69b654879f9d65264ca2631f6b0267eed6283",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/SCRUB LORENZA.jpg
            "0383e953204841257dfda726e35c74ffd8fe0b3dfaa41a38b653ab2b4c5eefe5",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/png سكراب/1-removebg-preview.png
            "ba8ec39d9d73986f6a46e4ac7055a3a3d92feef505615f2e01b0e7620287ed63",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/png سكراب/2س-removebg-preview.png
            "bb6276a035c969ac64fd367e4cd15b2d81b13b3b000adc10d6343b45f8d0fdf4",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/png سكراب/3س-removebg-preview.png
            "04257f0927dbcedd166ecd3c7d1093cc957004a07d746ff7e806056778e833c1",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/png سكراب/4س-removebg-preview.png
            "24a7f372b57caa4e046937a9f003457b33b96f33be34b0a3180389502e7c0e79",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/png سكراب/5س-removebg-preview.png
            "7e21000e72b04689d6d3b635989968cddc27e604268cc7d4713cf13c8c2fce00",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/scrub mokup.psb
            "ddea9f400de6c8b4436f923aefc28a94bbcf2a8ebb2c911ff7c42faab5cd6c42",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/12.psd
            "71557ae693997816610b42285966b06808fc2a25199f50f390eabaa7c836286c",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/Bottle_01_01.psd
            "b285bf9a176e4d1616ba8bceeb80026a02f7cf0f64572472bed2cba7fa5d1dba",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/SHAMPOO 11111.jpg
            "aa44cb61cae69733429a1fb122ba91132c411eef41be81d36877dc76edbf77a6",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/SHAMPOO [Recovered].ai
            "ae9bcffb8a8038a04a78d53683079e6aa3b66a19038c3c46c6171d53725b10c3",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/V.C.psd
            "182e37398d751129ebf9c8a081566c3bb6335e8012b83bf746f93a1e215cd4aa",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/shampoo lorenza.jpg
            "6601f36daf0b39e1676fc83ab6c3e331f8b5a259e31a379c39e8b803e2b86a99",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/shampoo.psd
            "7aa0bd4045318b980337c0c8ee4a03d000f8eacc98193cca152fac4bae79766a",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shower gel lorenza/shower gel lurenza.ai
            "41bec38b3036ab1bc38d3ef702df282fef91e81aa363193e3e036ec948270633",
            # materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shower gel lorenza/shower gel lurenza.jpg
            "73d6bef1d88bdc74cb09ab19034608cf59d032fb3bcc09da197f513e38727bc7",
        ),
        # the scope: the pack the text sits beside — a byte-identical copy elsewhere is not raised (§BH36(b))
        "paths": (
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/BATH OIL/bath oil lorenza.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/BATH OIL/bath oil lorenza.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/FACE OILE/FACE OIL LORENZA .ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/FACE OILE/FACE OIL LORENZA .jpg1.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/FACE WASH FOAM/FACE WASH FOAM.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/FACE WASH FOAM/FACE WASH FOAM111.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/Hair conditioner/1.psd",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/Hair conditioner/Hair conditioner lorenza.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/Hair conditioner/Hair conditioner.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/Hair conditioner/Hair conditioner.jpg222.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/LIP PALM LORENZA0/LIP PALM  LORENZA.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/LIP PALM LORENZA0/LIP PALM LORENZA0.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/NIGHT DAY CREAM 1/NIGHT & NIGHT CREAM LORENZA.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/NIGHT DAY CREAM 1/NIGHT & NIGHT CREAM LORENZA.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/SUN SCREEN LORENZA/SUN SCREEN LORENZA.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/SUN SCREEN LORENZA/SUN SCREEN LORENZA.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/body wash/body wash lorenza.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/body wash/body wash lorenza.jpg1111.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day and night 2 lorenza/day and night cream 2 lorenza.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day and night 2 lorenza/day and night cream 2 lorenza.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day cream 2 lorenza/day cream 2.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day cream 2 lorenza/كريم نهاري لورنزا.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day cream lorenza/day cream lorenza.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day cream lorenza/day cream lorenza.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face serum lorenza/face serum lorenza..ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face serum lorenza/face serum lorenza..jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face wach lorenza3/FACE WACH 1.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face wach lorenza3/FACE WACH 1.jpglorenza 3.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face wash tube/face wash tube.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face wash tube/face wash tube.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face wash tube/غسول وجه جل.psd",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/hair oil lorenza/hair oil.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/hair oil lorenza/hair oil.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/hair serum lorenza/hair serum lorenza.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/hair serum lorenza/hair serum lorenza.jpg111.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/SCRUB LORENZA.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/SCRUB LORENZA.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/png سكراب/1-removebg-preview.png",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/png سكراب/2س-removebg-preview.png",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/png سكراب/3س-removebg-preview.png",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/png سكراب/4س-removebg-preview.png",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/png سكراب/5س-removebg-preview.png",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/scrub/scrub mokup.psb",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/12.psd",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/Bottle_01_01.psd",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/SHAMPOO 11111.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/SHAMPOO [Recovered].ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/V.C.psd",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/shampoo lorenza.jpg",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shampoo/shampoo.psd",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shower gel lorenza/shower gel lurenza.ai",
            "materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/shower gel lorenza/shower gel lurenza.jpg",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-08",
        "terms_class": "OWNER_DECLARATION",
        # own_work_declaration_bh39.json (§BH39(c)) beside the pack — §BH36 class table, ruled at §BH37
        "evidence_path": "docs/design_intelligence/dip0a/own_work_declaration_bh39.json",
        "evidence_sha256": "06d9cfcc324935898d0eaea4f0b7fbf0b901b231d3847cf536523cf84598943a",
        "condition": "",
        "file_sha256s": (
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G01.ai
            "6b77164235801af6eb22d07048a2d22adf4ced393456a0267db24c7dffe700e8",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G01.jpg
            "7ee13fa37ef483f96cdf6f375ad0448bac27eb6689a78b72d7c1b3a71b86cb99",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G02.ai
            "b85025ffdbbbd4945ef820ea977cd8489401b83e1d1296dcc493def41fe38c25",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G02.jpg
            "1f338379a2bf14d0c90908e7d07f186bbceaa9a2bfa49ea2e4d43a4ed9c79072",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G03.ai
            "6e7d39f4d26e35f5b5928039458e43341856e3f772c8002c8701065725decaf4",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G03.jpg
            "525d0816cfc97cd0c10905e56cfb9368e63422ffab44edfc5c5db357a56900db",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G04.ai
            "29e44daefc5c7b77e59fc46d940e53edeb9524da6e3cabdca60d0729899f2a8a",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G04.jpg
            "ec3bef5f58bd01f7266a5147cd8629a30892375abd6a1f060db157cb8bf9c753",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G05.ai
            "6d6b8007b7c8c28c92f675ef448bbb1c5538e8bcdadedc36b945b325d3725e15",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G05.jpg
            "f746c4d1cede35cc507c85c1f9a62f5ff7cef8cb83b62579b8e9279370c4f265",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G06.ai
            "94793d6a428fe3ca3202565dfb10bf1a9820e04c0a11e512bd954daba4bdd479",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G06.jpg
            "587256de6ba41cbe5043a459b33dd2fdc41a9b46166924e23c23ba6d9adf4880",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G07.ai
            "26206856e34104de269ca0487f946746b7ab451fe5c364d39984b384f9b5eba9",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G07.jpg
            "3fd1dc179446f50225e8e0f0195cc02a762c7c05285c04f66bd10b8ac7c5937f",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G08.ai
            "0f733be5f3626d8d2899d4d2895a22e70cc66ad06ee597502e551f17b0e6a29a",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G08.jpg
            "51f4742be095aea02855eecdba02d107d4dc51978d9d3ae0b93a6b7c4b43c306",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G09.ai
            "8be06b1a5d560dc48280a3d3f5668820c4c34245c27e4ceddd9264dd2e436648",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G09.jpg
            "3196d92ed375e759b81980bdb9856be2324fc76a81e806899e5466cd3075c897",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G10.ai
            "9433b6e3b135eb56fc8fc5525ecbd0543cdd02a84b9653430e76cdfc6557a7cd",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G10.jpg
            "4f1af9ab13a2b11147302c5959567cb10d266f8e8b31e6e166bf804bd446553d",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G11.ai
            "bdc62173d47620c370dda2fad14e06c2c7e5fa52b7594c778011743e0d7f39fe",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G11.jpg
            "46644cb1dfa8c8beffae59b5d91028550965e0d8b7d7034980be5f9b865525b8",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G12.ai
            "40e7e0de2104b411ec224379dc8f93292b69ece5e577666dbf8042d91127ba81",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G12.jpg
            "12e843d6b1d5a5fea6dae820fe6403bfba192e7fd15981ed6519a500aa306403",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G13.ai
            "2a2dddf7d10f6d113ab78b77dea81d37d9dfe4b75109e8c2f889d1ad90aafe14",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G13.jpg
            "2f184e42512cc00da703c76aae342580915f301d31d14a62bf08c55e657973ef",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G14.ai
            "0b301445d4b9a2df617c4932604c0ccb2e1400ca677b3023cc8a30292edaf8d6",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G14.jpg
            "71cc486d6469582e0c48e594e60b47ac0907e315f90854e1bfd4d856b4978a10",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G15.ai
            "fddf4ff55201c59869c1e4b44a299a86f2539df33fee19fcf28e75c26f2d3b52",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G15.jpg
            "abc73eb8f08ba1217f897d710b955249c605873add253eec038fd0f808362900",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G16.ai
            "cfc23f5303cec2b6598daa9a29ea0d328f0930a0842f03938df62f17c0079462",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G16.jpg
            "3a5cd160e10a6d3134c668958d9ff57a8b1a8d5e3fbf3ebe9144bc553b134de2",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G17.ai
            "64735c8a3fd84aed865d7851719e6a7c0f83a0d6eed8cd7d86d86e0303e3f74b",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G17.jpg
            "0175fb4aed7a24d672b3ae536f3b0d2dfe9dcd7bee985c5fd4275d0da1e77a26",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G18.ai
            "3dccc640d0f6d9141b3ffbf8e345b5797c07626c8ebfd8c7937cd75668939b49",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G18.jpg
            "5430baf5365d68181dd867cbc66371b99dfe89b7cb1306ea6b307ed0a56cddbb",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G19.ai
            "f5b40c3718b271ef8c6d53593272221fc67ab9eedb5d7c8d6c672cc78ecdfacb",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G19.jpg
            "b4634d76b8da8ea6d0f2af027d569365ca0c11d93d92f5ad8b22d0a9e40badfa",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G20.ai
            "59afddaa8bbc80c5782bcf73150a2c58e8b729963aaad77c1e11f6a128c3ff96",
            # materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G20.jpg
            "9de0b211479fed72826e3f7261e99d0fb4da064768beb266873ea93cd0ccb615",
        ),
        # the scope: the pack the text sits beside — a byte-identical copy elsewhere is not raised (§BH36(b))
        "paths": (
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G01.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G01.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G02.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G02.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G03.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G03.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G04.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G04.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G05.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G05.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G06.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G06.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G07.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G07.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G08.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G08.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G09.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G09.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G10.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G10.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G11.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G11.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G12.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G12.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G13.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G13.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G14.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G14.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G15.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G15.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G16.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G16.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G17.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G17.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G18.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G18.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G19.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G19.jpg",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G20.ai",
            "materials/17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون/G20.jpg",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-08",
        "terms_class": "OWNER_DECLARATION",
        # own_work_declaration_bh39.json (§BH39(c)) beside the pack — §BH36 class table, ruled at §BH37
        "evidence_path": "docs/design_intelligence/dip0a/own_work_declaration_bh39.json",
        "evidence_sha256": "06d9cfcc324935898d0eaea4f0b7fbf0b901b231d3847cf536523cf84598943a",
        "condition": "",
        "file_sha256s": (
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/FACE POWDER
            "a775d04891ccaf2bd6d9c46547031cb3e49685e42b66e6638a260c1dc7666227",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/FACE POWDER BLACK.ai
            "934df57da826473adde98f31e3cfcfd2526dedaa5f265ea366f4dea63924f7fd",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/FACE POWDER BLACK.jpg
            "6ca2fc6c0b4bd6755a6457afbab4f68796fe3652a04723b226ae6baf254a95c5",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/FACE POWDER.jpg
            "b296ac48b9093b1545a7d5a902479c61fcedf2ae64cb17fbc30fed86e0a9661b",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/PLUSH.ai
            "4c1a92de97dae0cd2ac7d76bf3a5021d2ccce884a9a2a4a9d92898fdb01ddde2",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/PRIMER.ai
            "5d1b3bfc24bd6d4d29eba854e9dace4d9cdf1a4b689fc985e442a4f0db45cc6c",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/foundation 2.ai
            "b9829d97e0980efa458141d42901138cc3c084385fe74c386f7b330bc9b9721f",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/foundation2.jpg
            "9fd78624f57606a8efc1350ab0def219ed4267183f78b92e8c96a24f17de7a67",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/lip gloss black.ai
            "b55bb854b80fc4b3ffb3313a97c0b37f3915c151e88f1f7b7f1e00fad0b0651f",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/lip gloss black.jpg
            "85e0aad6ec6592054870a2ca1d37efab951f73cd1a61b338edb2f08263a17b27",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/lip gloss خمري.jpg
            "f07b8627e19e97992386c3795ecf50d7782b07560d05ba36304ed951f4432ade",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/lip glossخمري 2 .ai
            "d683be762b7aa82988c259094cf291770ad0df66aa5e679a3e2d5ee897b9785d",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/lip plump.ai
            "8c00bca50a430e90407db3bd7695aefd0db0ca2eb1552cdf33ac7888f8d07d69",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/lip plump.jpg
            "d898681e78fe257af02aac2339e28e802232c18e72e391017930e15f88ed7db2",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/magic lipstick.ai
            "c5b29fa812233e168a2faaae5c7a5b3e9223a7df66dba3a669709bc2fae2fbdb",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/magic lipstick.jpg
            "160a788520386bdb20c6e4330acd44658e092a258af44ff7355ca33c45c7892d",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/plush.jpg
            "88ee83b70a61e81afa0c31bd458ea362dcd443cb81b44168649e9f003468aed0",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/primer.jpg
            "169a865b146be32d89ee72c0b77552ba34fc6e701e2aad34b8d4fccadd1cb139",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/CONCEALER.ai
            "cf882139cc09e17f35b585b4539dda0cc10d5689cb462a5be8a058e4eb16e2df",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/CONCEALER.jpg
            "2172e8b9e153ff15f446b305b97d985001b48c7109b4d9206cae258163374738",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/FOUNDATION.ai
            "57e8fa46c3000f616bc02073f18ad8078449199de85cbd14189d36d96cd80393",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/FOUNDATION.jpg
            "4a8cb6edfb247d67523bfdc1774c69110944ceb1025e1bd73a0a9580d025f257",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP GLOSS 1.ai
            "30856fc88aa3685f75f6a2abacabbc04d113672a374a9c3ed787776298654abb",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP GLOSS 1.jpg
            "f3ab921ee9eeb4a103330d76ebf11842503ecf7afbf204ff99d2b2e39c6bff4c",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP GLOSS 2.ai
            "34b9c018eaafa159c443c18452012815cca25848a443c939889109b984624e94",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP GLOSS 2.jpg
            "4060df5e04df3b9b023e513e5d1c0b207486e3da3dd0dfc45a5362037653ab0a",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP OIL.ai
            "8f3e70f9eb9a32bef515e681973074857faff689b6a5cd71326a1b7a439b62f2",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP OIL.jpg
            "ad1215d099b1419ef0b114afd0521c72132657d7ce429785609ad536c6ee9d6e",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP STICK.ai
            "9861ecccd334008b61345e8ae67755d2c1830ead163a749815499ea3a4a1b203",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP STICK.jpg
            "bdb0e85244d69ad6b6fea4cd5769f11c00bad5d5f995e2c58d842b4e0b51824f",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/MASCARA.ai
            "359335343db71420370ef01bf4cebc7828478f764955e40bbcd7b58c9b9fb1bc",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/face powder.ai
            "8b429ffb0eaaea4b85afefa2b1f4a21d8151e68602516a0a9face60cbd89f18a",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/face powder.jpg
            "6ec694efa6ef3c2a578efe110af251d5e3748f5a6527fc9804998c0e0309f87f",
            # materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/loose powder feonka.ai
            "6585901b6a32c91c7e8237ca8a389f2d7fe83478923578170460692cf3531c8d",
        ),
        # the scope: the pack the text sits beside — a byte-identical copy elsewhere is not raised (§BH36(b))
        "paths": (
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/FACE POWDER",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/FACE POWDER BLACK.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/FACE POWDER BLACK.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/FACE POWDER.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/PLUSH.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/PRIMER.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/foundation 2.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/foundation2.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/lip gloss black.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/lip gloss black.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/lip gloss خمري.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/lip glossخمري 2 .ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/lip plump.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/lip plump.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/magic lipstick.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/magic lipstick.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/plush.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/lama/primer.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/CONCEALER.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/CONCEALER.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/FOUNDATION.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/FOUNDATION.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP GLOSS 1.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP GLOSS 1.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP GLOSS 2.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP GLOSS 2.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP OIL.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP OIL.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP STICK.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/LIP STICK.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/MASCARA.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/face powder.ai",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/face powder.jpg",
            "materials/17-10-2024/Telegram Desktop/feonca 5 to jouman/feonca 5 to jouman/جيجي/فيونكا 5/loose powder feonka.ai",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-05",
        "terms_class": "ATTRIBUTION-REQUIRED",
        # License free.txt beside the pack — §BH36 class table, ruled at §BH37
        "evidence_path": "materials/17-10-2024/pile-online-shopping-package-mockups/License free.txt",
        "evidence_sha256": "ce8a9fa638b586e060bf4a787f80b1a6f562874a3663d9d2d8ad06af6b9d289c",
        "condition": "<a href=\"http://www.freepik.com\">Designed by rawpixel.com / Freepik</a> | \"Designed by rawpixel.com / Freepik\"",
        "file_sha256s": (
            # materials/17-10-2024/pile-online-shopping-package-mockups/65757.jpg
            "296ec6dfc1ff639c5e86ab05cd57d67d10ded221179f527bb76d2e294a04ea58",
            # materials/17-10-2024/pile-online-shopping-package-mockups/65757.psd
            "23aa600b4b614d2bc6b825d9b383f646c310279be861bcc85136c9c5c6e78725",
        ),
        # the scope: the pack the text sits beside — a byte-identical copy elsewhere is not raised (§BH36(b))
        "paths": (
            "materials/17-10-2024/pile-online-shopping-package-mockups/65757.jpg",
            "materials/17-10-2024/pile-online-shopping-package-mockups/65757.psd",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-05",
        "terms_class": "ATTRIBUTION-REQUIRED",
        # License free.txt beside the pack — §BH36 class table, ruled at §BH37
        "evidence_path": "materials/ALL..MOCKUP/27-4-2024/delicious-summer-fruits/License free.txt",
        "evidence_sha256": "a8f5fa92a29eaca875e41594b3f3942e9724f5ea3de660c282a3dcf7e0528eea",
        "condition": "<a href=\"http://www.freepik.com\">Designed by Freepik</a> | \"Designed by Freepik\"",
        "file_sha256s": (
            # materials/ALL..MOCKUP/27-4-2024/delicious-summer-fruits/116297-OPHTK5-790.eps
            "5620082f8c8caca1c425f3227b94fde96ab6a04b511264a3b66d2189569b3a7a",
            # materials/ALL..MOCKUP/27-4-2024/delicious-summer-fruits/116297-OPHTK7-614.jpg
            "534db7ec8e7248406f6a95609a6688c6a28a5bdf438c6eb9380991dd1bc3d458",
            # materials/ALL..MOCKUP/27-4-2024/delicious-summer-fruits/116297-OPHTKC-8.ai
            "8862cc65dcc146a5a777eefae04ff09fef0519ce51d2d84b98ba7ab11d5d63f1",
        ),
        # the scope: the pack the text sits beside — a byte-identical copy elsewhere is not raised (§BH36(b))
        "paths": (
            "materials/ALL..MOCKUP/27-4-2024/delicious-summer-fruits/116297-OPHTK5-790.eps",
            "materials/ALL..MOCKUP/27-4-2024/delicious-summer-fruits/116297-OPHTK7-614.jpg",
            "materials/ALL..MOCKUP/27-4-2024/delicious-summer-fruits/116297-OPHTKC-8.ai",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-05",
        "terms_class": "ATTRIBUTION-REQUIRED",
        # License free.txt beside the pack — §BH36 class table, ruled at §BH37
        "evidence_path": "materials/ALL..MOCKUP/27-4-2024/green-packaging-cosmetic-products(2)/License free.txt",
        "evidence_sha256": "a8f5fa92a29eaca875e41594b3f3942e9724f5ea3de660c282a3dcf7e0528eea",
        "condition": "<a href=\"http://www.freepik.com\">Designed by Freepik</a> | \"Designed by Freepik\"",
        "file_sha256s": (
            # materials/ALL..MOCKUP/27-4-2024/green-packaging-cosmetic-products(2)/2512866.psd
            "0e030f40f0ec0b0f696a55be81e552f56111b4bef4ea294d00fee6458d589231",
            # materials/ALL..MOCKUP/27-4-2024/green-packaging-cosmetic-products(2)/2512865.jpg
            "873e0cd3b369cf2c93ce4277f9440c7515c4c0a8080bb2fc780feeec644844ed",
        ),
        # the scope: the pack the text sits beside — a byte-identical copy elsewhere is not raised (§BH36(b))
        "paths": (
            "materials/ALL..MOCKUP/27-4-2024/green-packaging-cosmetic-products(2)/2512866.psd",
            "materials/ALL..MOCKUP/27-4-2024/green-packaging-cosmetic-products(2)/2512865.jpg",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-05",
        "terms_class": "ATTRIBUTION-REQUIRED",
        # License free.txt beside the pack — §BH36 class table, ruled at §BH37
        "evidence_path": "materials/ALL..MOCKUP/27-4-2024/logo-mockup-luxury-box/License free.txt",
        "evidence_sha256": "507d4668a6bd7da0de851cb645adb27b0a1d143d847b40cd5cc29dcb0d6f589b",
        "condition": "<a href=\"http://www.freepik.com\">Designed by asylab / Freepik</a> | \"Designed by asylab / Freepik\"",
        "file_sha256s": (
            # materials/ALL..MOCKUP/27-4-2024/logo-mockup-luxury-box/130.psd
            "90f8f7b6cea27c78d8165fe74e94bd0fde415d2f6b4521c12e46b4fd0ea236b5",
            # materials/ALL..MOCKUP/27-4-2024/logo-mockup-luxury-box/130.jpg
            "212db6cb587cb3b574b18b8341f678a31e6270332fa58f85a9de350c2b9f30fd",
        ),
        # the scope: the pack the text sits beside — a byte-identical copy elsewhere is not raised (§BH36(b))
        "paths": (
            "materials/ALL..MOCKUP/27-4-2024/logo-mockup-luxury-box/130.psd",
            "materials/ALL..MOCKUP/27-4-2024/logo-mockup-luxury-box/130.jpg",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-05",
        "terms_class": "ATTRIBUTION-REQUIRED",
        # License free.txt beside the pack — §BH36 class table, ruled at §BH37
        "evidence_path": "materials/ALL..MOCKUP/عبوات مواد تجميل/cosmetics-package-realistic-transparent-set/License free.txt",
        "evidence_sha256": "a8691bdbf3603356d4af4015b19d1f19cc4d436656df262c70f56e71ef75ac4e",
        "condition": "<a href=\"http://www.freepik.com\">Designed by macrovector / Freepik</a> | \"Designed by macrovector / Freepik\"",
        "file_sha256s": (
            # materials/ALL..MOCKUP/عبوات مواد تجميل/cosmetics-package-realistic-transparent-set/18207.eps
            "f638f962fb01d29a14bd9f54621a3502ba3baf2b9c6a24428981e4a5c1c2b0ac",
            # materials/ALL..MOCKUP/عبوات مواد تجميل/cosmetics-package-realistic-transparent-set/18207.jpg
            "ab565393a137e0f4cec2d0f75763611d97acb3ff1bd1fc9429e7e23ce615c0fa",
        ),
        # the scope: the pack the text sits beside — a byte-identical copy elsewhere is not raised (§BH36(b))
        "paths": (
            "materials/ALL..MOCKUP/عبوات مواد تجميل/cosmetics-package-realistic-transparent-set/18207.eps",
            "materials/ALL..MOCKUP/عبوات مواد تجميل/cosmetics-package-realistic-transparent-set/18207.jpg",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-05",
        "terms_class": "ATTRIBUTION-REQUIRED",
        # License free.txt beside the pack — §BH36 class table, ruled at §BH37
        "evidence_path": "materials/ALL..MOCKUP/عبوات مواد تجميل/makeup-realistic-items-super-set-with-mascara-powder-isolated-vector-illustration/License free.txt",
        "evidence_sha256": "a8691bdbf3603356d4af4015b19d1f19cc4d436656df262c70f56e71ef75ac4e",
        "condition": "<a href=\"http://www.freepik.com\">Designed by macrovector / Freepik</a> | \"Designed by macrovector / Freepik\"",
        "file_sha256s": (
            # materials/ALL..MOCKUP/عبوات مواد تجميل/makeup-realistic-items-super-set-with-mascara-powder-isolated-vector-illustration/16260.eps
            "3a8f22e2c239cecc95cd5a0d4327deeb3627f7e7315b0749549b664254f5815f",
            # materials/ALL..MOCKUP/عبوات مواد تجميل/makeup-realistic-items-super-set-with-mascara-powder-isolated-vector-illustration/16260.jpg
            "415b5255d80263b919c0e41f31b5e1058fd01db44f79e3f291f192adb1e98507",
        ),
        # the scope: the pack the text sits beside — a byte-identical copy elsewhere is not raised (§BH36(b))
        "paths": (
            "materials/ALL..MOCKUP/عبوات مواد تجميل/makeup-realistic-items-super-set-with-mascara-powder-isolated-vector-illustration/16260.eps",
            "materials/ALL..MOCKUP/عبوات مواد تجميل/makeup-realistic-items-super-set-with-mascara-powder-isolated-vector-illustration/16260.jpg",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-05",
        "terms_class": "ATTRIBUTION-REQUIRED",
        # License free.txt beside the pack — §BH36 class table, ruled at §BH37
        "evidence_path": "materials/ALL..MOCKUP/عبوات مواد تجميل/nail-polish/License free.txt",
        "evidence_sha256": "137c349d04122ed953b32d323fb08a178c8e5b526f5f57e583ae0e90dd3d0a8e",
        "condition": "<a href=\"http://www.freepik.com\">Designed by macrovector_official / Freepik</a> | \"Designed by macrovector_official / Freepik\"",
        "file_sha256s": (
            # materials/ALL..MOCKUP/عبوات مواد تجميل/nail-polish/7077.eps
            "f53bb4388485831adfedbfb98dbb2b9ffb4da5b973f2da0ec45ff197e525c6e9",
            # materials/ALL..MOCKUP/عبوات مواد تجميل/nail-polish/7077.jpg
            "a52e8b84cdc1f08d667a8f9ec402e225ac400a0b7fad45f6ec7edffc3962ab7d",
        ),
        # the scope: the pack the text sits beside — a byte-identical copy elsewhere is not raised (§BH36(b))
        "paths": (
            "materials/ALL..MOCKUP/عبوات مواد تجميل/nail-polish/7077.eps",
            "materials/ALL..MOCKUP/عبوات مواد تجميل/nail-polish/7077.jpg",
        ),
    },
)


def _measured_evidence_sha256(grant: dict) -> str | None:
    """The evidence file's sha256 as it is NOW — re-hashed on every application."""
    p = Path(grant["evidence_path"])
    if not p.is_absolute():
        p = REPO_ROOT / p
    from apps.ire.materials_paths import resolve_material_file, MaterialPathError
    try:
        p = resolve_material_file(p, repo_root=REPO_ROOT)
    except MaterialPathError:
        return None
    return sha256_of_file(str(p))


def apply_material_grants(record: dict, *, grants: tuple = None) -> dict:
    """Apply the owner grants to a ``materials_tier/1.0`` record.

    Returns a NEW record; the input is never mutated. For each row the FIRST
    grant naming its sha256 governs. A malformed grant applies to nothing; a
    grant whose evidence no longer hashes to its pinned sha256 is VOID and the
    row keeps its machine tier (REFERENCE) — recorded on the row so the void is
    visible, never silent.
    """
    applied = MATERIAL_GRANTS if grants is None else tuple(grants)
    applied = tuple(g for g in applied if isinstance(g, dict)
                    and not any(not g.get(k) for k in _REQUIRED_FIELDS))
    rows = list(record.get("rows") or [])
    if not rows or not applied:
        return dict(record)
    measured_by = {id(g): _measured_evidence_sha256(g) for g in applied}
    new_rows = []
    for row in rows:
        sha = (row or {}).get("sha256")
        path = (row or {}).get("relative_path")
        grant = next((g for g in applied if sha in frozenset(g["file_sha256s"])
                      and (not g.get(SCOPE_FIELD) or path in frozenset(g[SCOPE_FIELD]))), None)
        if grant is None:
            new_rows.append(row)                       # unnamed, or named but out of scope: untouched, REFERENCE
            continue
        measured = measured_by[id(grant)]
        if measured != grant["evidence_sha256"]:
            rec = dict(row)                            # VOID: the machine tier stands
            rec["tier"] = machine_writable_tier(TIER_REFERENCE)
            rec["grant_void"] = (f'evidence {grant["evidence_path"]} hashes to '
                                 f'{measured or "unreadable"}, grant pins {grant["evidence_sha256"]}')
            new_rows.append(rec)
            continue
        rec = dict(row)
        rec.update({
            "tier": TIER_PRODUCTION,                   # the grant honoured: OWNER DATA
            "tier_source": TIER_SOURCE_OWNER_GRANT,
            "evidence": f'{grant["evidence_path"]} sha256:{measured}',
            "condition": str(grant.get("condition") or ""),
            "terms_class": grant["terms_class"],
            "granted_by": grant["granted_by"],
            "granted_at": grant["granted_at"],
        })
        new_rows.append(rec)
    out = dict(record)
    out["rows"] = new_rows
    out["all_machine_rows_reference"] = all(
        r["tier"] == TIER_REFERENCE for r in new_rows if r.get("tier_source") != TIER_SOURCE_OWNER_GRANT)
    return out


def production_rows(record: dict) -> list:
    """The rows the channel raised — each carries its evidence and condition."""
    return [r for r in record.get("rows") or [] if r.get("tier") == TIER_PRODUCTION]


__all__ = ["SCHEMA", "REPO_ROOT", "MATERIAL_GRANTS", "apply_material_grants", "production_rows"]
