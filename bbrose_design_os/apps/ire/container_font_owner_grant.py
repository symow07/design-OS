"""§BH26(a) — the OWNER-GRANT channel. Owner-conferred states enter as OWNER DATA.

THE CHANNEL IS NOT THE SEAM. ``machine_writable_verification`` and
``machine_writable_source`` govern what a MACHINE may write, and
``SEAM_REFUSED_VERIFICATIONS`` keeps refusing ``VERIFIED_FOR_PRODUCTION``
arriving through ``confirmed_fonts`` — all three stay byte-identical in
meaning. This module carries something categorically different: a grant the
OWNER typed, transcribed at OWNER_BLOCKER_CLEARANCE.md §BH26, conferring
states only a human may confer. The machine's job here is not to decide but
to CHECK, fail-closed, that the grant's own conditions still hold at every
application:

  (i)  the licence file is RE-HASHED on every application; unreadable or a
       hash other than the pinned one ⇒ the grant is VOID ⇒ each face the
       grant names falls back to LICENCE_REVIEW_REQUIRED — a MACHINE value,
       written through the MACHINE guard, never an error-shaped pass and
       never a conferred state;
  (ii) a face whose measured sha256 the grant does not name gets NOTHING
       from the channel — it is returned untouched;
  (iii) a grant missing any required field applies to nothing.

The conferred states are OWNER DATA. The machine guards are deliberately NOT
invoked on them: asking ``machine_writable_verification`` to pass
``VERIFIED_FOR_PRODUCTION`` would be asking the ceiling to move, which is
§BH26's first hard stop. The guard runs only on the VOID path's machine
value, where it already permits ``LICENCE_REVIEW_REQUIRED``.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from apps.ire.container_font_authority import (
    LICENCE_REVIEW_REQUIRED,
    SOURCE_USER_CONFIRMED,
    SOURCES_CLEARING_FALLBACK,
    VERIFIED_FOR_PRODUCTION,
    machine_writable_verification,
)

SCHEMA = "container_font_owner_grant/1.0"

#: §BH26(a), the owner's typed grant — single-use authority, spent on the
#: landing of the commit that carries this module. "For EXACTLY the two
#: faces, identified by file sha256 and nothing else." The evidence is the
#: OFL.txt the owner read under §BH12(a), staged by §BH25, pinned by path
#: AND hash; §BH25's measurement resolved BOTH faces to this ONE file.
OWNER_GRANT_BH26 = {
    "schema_version": SCHEMA,
    "granted_by": "BBrose",
    "granted_at": "2026-09-01",
    "licence_id": "OFL-1.1",
    "licence_evidence_path": str(
        Path(__file__).resolve().parents[2] / "static" / "fonts" / "OFL.txt"),
    "licence_evidence_sha256":
        "f2095b08bed08b23a6fe26112fcd679a2bee3f002eef077eb05d215ed1051bd8",
    "face_sha256s": (
        # NotoSans-Regular.ttf
        "478c558ea716033cd60c03438f628dfa75694dcf6b5f6d505a2f05fd2b4f3823",
        # NotoSans-Bold.ttf
        "1df075a380fc7cb898acf64c1f7b3b4dd780de3caa860178bf929de35817a913",
    ),
}

#: §BH32(c), the owner's conditioned grant for the sticker path's Arabic face — single-use
#: authority, spent on the landing of the commit that carries this row. Conditions measured
#: before the row was written (2026-09-04, archive/work/bh32_font_wiring_build/naskh_evidence/record.json): the local file
#: hash-matches the notofonts upstream release NotoNaskhArabic-v2.021 (NotoNaskhArabic/hinted/ttf/NotoNaskhArabic-Regular.ttf build,
#: sha256 6f0a92031367b2f5…); the licence beside it upstream (OFL.txt, body sha256[:16]
#: d3038c5fe4cef3bc) has a body — the text after the copyright line — byte-identical
#: to OFL 1.1 bodies the owner read at §BH29 (Merriweather, Roboto), so the
#: owner's reading extends to it. The evidence pinned here is the licence committed BESIDE the
#: face in cbcf4ac, static/fonts/OFL.txt — the body the owner read complete at §BH25 and the file
#: the Noto pair's grant already pins — by path AND hash; its wording differs from the upstream
#: body only in the OFL 1.1 boilerplate's FAQ URL and line wrapping (recorded in record.json).
OWNER_GRANT_NASKH = {
    "schema_version": SCHEMA,
    "granted_by": "BBrose",
    "granted_at": "2026-09-04",
    "licence_id": "OFL-1.1",
    "licence_evidence_path": str(
        Path(__file__).resolve().parents[2] / "static" / "fonts" / "OFL.txt"),
    "licence_evidence_sha256":
        "f2095b08bed08b23a6fe26112fcd679a2bee3f002eef077eb05d215ed1051bd8",
    "face_sha256s": (
        # NotoNaskhArabic-Regular.ttf (Noto Naskh Arabic 2.021, notofonts/arabic)
        "6f0a92031367b2f5a2078fe9d24f3433122b61a0bad57c423aad8f3c39aa2e6e",
    ),
}

_BRAND2026 = Path(__file__).resolve().parents[2] / "static" / "fonts" / "brand2026"

#: §BH30(d) — the open-set grants, ONE ROW PER FACE keyed by its sha256 (the ruling's words),
#: the licence text that shipped beside it pinned by path and sha256; every sha256 below was RE-MEASURED from the in-corpus bytes when this
#: tuple was generated (2026-09-04); the evidence is re-hashed on every application.
#: The Noto pair keeps its own grant above; no sha256 appears in two grants (tested).
OWNER_GRANTS_BH30 = (
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Amatic_SC" / "OFL.txt"),
        "licence_evidence_sha256": "301f77908df2b00141b4dcea50cc1a586c3afcee78843bd811088e8263623f9d",
        "face_sha256s": (
            # Amatic_SC/AmaticSC-Bold.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "d367beadee66efbb657d24d3d8f30f3b60633e9d5c8ded7385541cf775cabb4d",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Amatic_SC" / "OFL.txt"),
        "licence_evidence_sha256": "301f77908df2b00141b4dcea50cc1a586c3afcee78843bd811088e8263623f9d",
        "face_sha256s": (
            # Amatic_SC/AmaticSC-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "513a76f96d39a5366bd27c258674aaea35ee51c42b8f3060387f74649ee8c8aa",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Bebas_Neue" / "OFL.txt"),
        "licence_evidence_sha256": "72082f6cb4d04be2ecf7cc7d9e1e7d73787f0af8a5a278a47cade70c16b78341",
        "face_sha256s": (
            # Bebas_Neue/BebasNeue-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "08e4623805102d819f58601e46e345648846075e363b2ceb23313c2d1c83ec73",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Cairo" / "OFL.txt"),
        "licence_evidence_sha256": "17b90cece30db64934b7299fd76b033a3774c8a990e78badc74c59a5be8e0727",
        "face_sha256s": (
            # Cairo/Cairo-Bold.ttf (LIBRARY_COPY_HASH_MATCHED)
            "1936f28abe143ff104b2320157195fbc333bbdc52acf927c1353dbaeaeee7c16",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Grand_Hotel" / "OFL.txt"),
        "licence_evidence_sha256": "4c0a1150a363b42bd8681ff4a00315ac49510a944c4c9978237ff8b90a8920a5",
        "face_sha256s": (
            # Grand_Hotel/GrandHotel-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "ec7ae65d49c936cb5ed32534ab74dbd40c56733de5145ac3aae9da362e02b50f",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Great_Vibes" / "OFL.txt"),
        "licence_evidence_sha256": "61093a21f5e63dedf54222b3c09997e54c0fe43e3851d21386e02ddcbc246d49",
        "face_sha256s": (
            # Great_Vibes/GreatVibes-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "8d509802186f1b51572531ecf313e8098f9a5bfdfaca93f0c9b34467f9982d15",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Lato" / "OFL.txt"),
        "licence_evidence_sha256": "74ba064d03f1f1c4a952da936c3eb71866c34404916734de3cae73b34357e59e",
        "face_sha256s": (
            # Lato/Lato-Black.ttf (LIBRARY_COPY_HASH_MATCHED)
            "8b32bc539ca95dda2d2206a43234b5f3b0fe964bd25966c860bc80ec7f06d702",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Montserrat" / "OFL.txt"),
        "licence_evidence_sha256": "8b7141c03fa4f8d44e6345d5d4931709290f0f67875e452e95ac1fd3a027802e",
        "face_sha256s": (
            # Montserrat/Montserrat-Italic[wght].ttf (ACQUIRED_UPSTREAM_RELEASE)
            "51607f316bc020e59f03cbf51543eecffbea501c0b31d73e5b82927c5cca442c",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Montserrat" / "OFL_at_9548902f.txt"),
        "licence_evidence_sha256": "41f82bb4d24b304f30f7136bc47abdd083782e4265c984160f5649d1e78ea49c",
        "face_sha256s": (
            # Montserrat/Montserrat-Regular.ttf (LIBRARY_COPY_HASH_MATCHED)
            "81ebc3916b524007b756d91d9df13c7673ec401161f2cad161662d08dcf1cc72",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Montserrat" / "OFL.txt"),
        "licence_evidence_sha256": "8b7141c03fa4f8d44e6345d5d4931709290f0f67875e452e95ac1fd3a027802e",
        "face_sha256s": (
            # Montserrat/Montserrat[wght].ttf (ACQUIRED_UPSTREAM_RELEASE)
            "0f7b311b2f3279e4eef9b2f968bcdbab6e28f4daeb1f049f4f278a902bcd82f7",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "Apache License, Version 2.0",
        "licence_evidence_path": str(_BRAND2026 / "Open_Sans" / "LICENSE.txt"),
        "licence_evidence_sha256": "3ddf9be5c28fe27dad143a5dc76eea25222ad1dd68934a047064e56ed2fa40c5",
        "face_sha256s": (
            # Open_Sans/OpenSans-Semibold.ttf (LIBRARY_COPY_HASH_MATCHED)
            "aa3b0ef53db12e3d45094030cac0e69d384e44cc5978643dd4390041cad546e2",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Playfair_Display" / "OFL.txt"),
        "licence_evidence_sha256": "566be814f8e96e93dfa16101331557eb6b5467e9e03f627c0910fe93ca12300e",
        "face_sha256s": (
            # Playfair_Display/PlayfairDisplay-Italic[wght].ttf (ACQUIRED_UPSTREAM_RELEASE)
            "a5e26dc5e2e77fb2803a0bf02fd4f81ee136ec8dea863ccdb0c59a263b21378b",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Playfair_Display" / "OFL.txt"),
        "licence_evidence_sha256": "566be814f8e96e93dfa16101331557eb6b5467e9e03f627c0910fe93ca12300e",
        "face_sha256s": (
            # Playfair_Display/PlayfairDisplay[wght].ttf (ACQUIRED_UPSTREAM_RELEASE)
            "c40f2293766a503bc70cce9e512ef844a4ccb7cbcde792fe2ea31d191917d8d6",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-Black.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "d82aaaf98a9283f9a8edd24e51173337d8eaf09e25cd3d98831f8ec8461748a1",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-BlackItalic.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "f4852ca89c29f69d800e14f097ed4d1f0a0cc454e9f77d73bfd6db1f71c287a0",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-Bold.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "983676516167748b74de6f4771fb384c664fd913acb8b471122ecacf5da5ea6c",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-BoldItalic.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "3572ac8116a0ac7317d342262b29937bcbaf94d8f03f90df6fe666fa7e2fb43a",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-ExtraBold.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "f2ab17c1a63a0ecc12c2461848fc8a469395e3cd2d641803e889c643d9f958e1",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-ExtraBoldItalic.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "dc00a2eb988373e9f4e99bf8ff76c6315ee21d36b341cbbff024e4c18cc7ac03",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-ExtraLight.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "55c03314cc754e26f741f97890e5e9cbe3b3278fe3abcecfecafd60111b2643d",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-ExtraLightItalic.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "7171a17e4cda8f6ded78a7a931f9b7f38987057f3ffd1fe07a71528ad0f01e49",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-Italic.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "4fa76ae75b40f926420514044722cb97f32186cafd3b38263cc34dad7174d46d",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-Light.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "650ba57fa99d12ec40c31ccfb680be656be4497fbe14164617d67e32ffe9cd46",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-LightItalic.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "b8f9c5be59723fadf8e5447fa1245c2c53b60a3464a24d6ece9ee3c283d8917b",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-Medium.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "90373e7d838d32468438fc3e152dca0bdb12edcab99ea639f158790b1ba1fd05",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-MediumItalic.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "765addf6c7c11ec3c54325cacd68cabd05df8e4b6455302d812a9b9bafd1c614",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "7e65201e9b79159e2300267cc885e16c8dcef2424cdfa09a29bfb0980a94a7ba",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-SemiBold.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "d3bf1bdaf0550e83da9ac0b1d1d9fe6db086835a83aa28578e609a394b9a0286",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-SemiBoldItalic.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "16bb118aa232c9a13fa238027d24d7854dd1a1d9cbaf99b17fec4388d56b432c",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-Thin.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "6d8e5d9d29140cc93e321745fa1243c67889e6bc3639ec34db64f3da7a496352",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Poppins" / "OFL.txt"),
        "licence_evidence_sha256": "6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573",
        "face_sha256s": (
            # Poppins/Poppins-ThinItalic.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "46df80ac970f5e84829b868d283878b4d97e289c7b1245541d8bbf66b5d670a8",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Quicksand" / "OFL.txt"),
        "licence_evidence_sha256": "14d28541780d90f6577bb7abcc6f005bf6969614294e75c82abb8758a696ad46",
        "face_sha256s": (
            # Quicksand/Quicksand[wght].ttf (ACQUIRED_UPSTREAM_RELEASE)
            "39c9b64223561f56aaff6062a6f04063c4fc86809ad6768722c06614d977e1cc",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Raleway" / "OFL.txt"),
        "licence_evidence_sha256": "e588abf45ca2b19c340c4b27349c9b6b6e5e198316fd965128ed9f4422942cbe",
        "face_sha256s": (
            # Raleway/Raleway-Light.ttf (LIBRARY_COPY_HASH_MATCHED)
            "d11b6f8bbb1025a56e94141b4fe29ff6c8cd67c60a0adeb7165679e5fba70988",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Rubik" / "OFL.txt"),
        "licence_evidence_sha256": "3bf1a0fdd4210b875271e8dabaa55c0313a2c679a20f5f860bbe2adfc8f88e2f",
        "face_sha256s": (
            # Rubik/Rubik-Bold.ttf (LIBRARY_COPY_HASH_MATCHED)
            "6ed15b1bb0bff1c5a2f899b018a1b28c2ba664d1b6541692545ff1b677faf0f0",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-09-04",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Shadows_Into_Light_Two" / "OFL.txt"),
        "licence_evidence_sha256": "6a28d4d5d8b4d1ea89ace5a047ac6e0de182acdb8bfa22897bf7702102094f69",
        "face_sha256s": (
            # Shadows_Into_Light_Two/ShadowsIntoLightTwo-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE)
            "d2540170b1b1df3094de433b4632755ba91ecb65626202a3c8affd2245e08405",
        ),
    },
)

#: [the owner's answers after 117 was redrawn on his rules, 2026-10-02, answer 1: "Grant a SET of open-licence (SIL OFL)
#: fonts, downloaded only from Google Fonts' official source, licence and provenance recorded"; his second message:
#: "download all 39; grant Yellowtail and Satisfy under Apache 2.0"] the font set's grants, §BH30(d)'s way — ONE ROW PER
#: FACE keyed by its sha256, the licence text that shipped beside it upstream pinned by path and sha256 (Yellowtail and
#: Satisfy under Apache 2.0, the rest SIL OFL 1.1); every sha256 measured from the bytes as fetched once from the
#: google/fonts repository and recorded in PROVENANCE.json; the evidence is re-hashed on every application.
OWNER_GRANTS_2026_10_02 = (
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Pacifico" / "OFL.txt"),
        "licence_evidence_sha256": "a47e5daeda73568969395c656823102678f2eefb0d7d7ecb47aac4cc17e42204",
        "face_sha256s": (
            # Pacifico/Pacifico-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "5b6c0d5334a7bf77dea52b975c5a0c408878c0f7115ed5b6fb151f634b7bf701",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Lobster" / "OFL.txt"),
        "licence_evidence_sha256": "88aece7d90f2bb7049719f11619a560af22af3451af141f12aa4f46bb157a99b",
        "face_sha256s": (
            # Lobster/Lobster-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "d6568e697fd50cedc0be04d8aae4127fe95add607e7bff954ca88604be80c205",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "Apache License, Version 2.0",
        "licence_evidence_path": str(_BRAND2026 / "Yellowtail" / "LICENSE.txt"),
        "licence_evidence_sha256": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
        "face_sha256s": (
            # Yellowtail/Yellowtail-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "3e06841b13000975f3cc38aa84e326e601a4378a4c52d50b5e9fee3598c5d236",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Kaushan_Script" / "OFL.txt"),
        "licence_evidence_sha256": "3336bf5d4e7eedba48ecb831f37bf676e901c39f2e6a422cceadd9d2ffa55be8",
        "face_sha256s": (
            # Kaushan_Script/KaushanScript-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "6d8d379d9bba98178bee476d68114c8f83812c18005ecccf679e70f60e03d8f6",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Damion" / "OFL.txt"),
        "licence_evidence_sha256": "cf28b0c2cd8dea6aaec899baf5d050ef1f578daeaf51e931a934d100b4de9ecc",
        "face_sha256s": (
            # Damion/Damion-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "a51fd6c3c517feb9924b98139c2e902a7317caee52c22a2ec9682973969562bf",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "Apache License, Version 2.0",
        "licence_evidence_path": str(_BRAND2026 / "Satisfy" / "LICENSE.txt"),
        "licence_evidence_sha256": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
        "face_sha256s": (
            # Satisfy/Satisfy-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "55bb141a0a23a32278d5fa7fd2e853824faa173b94774660ebeddb106be07c80",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Dancing_Script" / "OFL.txt"),
        "licence_evidence_sha256": "6f090277c00af96651ce6dbcc38ff1591047a3bffef486e80b6a32e8276a8201",
        "face_sha256s": (
            # Dancing_Script/DancingScript[wght].ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "21808625578fe8d8cd10cb684be546dca077b27cd03a53a2f1ec11dc743c924c",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Cookie" / "OFL.txt"),
        "licence_evidence_sha256": "c832a4230a713d080aa2f2544d9a298ed911f689b2c48f7f276a0196b16d2b8a",
        "face_sha256s": (
            # Cookie/Cookie-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "9daf3cc9e5efe1b65094cdf1f14729ef6f07a70c27ee0679bf7f544a828b080e",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Shrikhand" / "OFL.txt"),
        "licence_evidence_sha256": "325e890b8b26fe0a683c3ba24c506d902bdd7034d9c47bd7fa2bb72b5433b9c9",
        "face_sha256s": (
            # Shrikhand/Shrikhand-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "8ba32f6d6a96fb8dbc92fc1acfbc4d2123d5348063d89b2c3dd784e7afcb81af",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Bagel_Fat_One" / "OFL.txt"),
        "licence_evidence_sha256": "4f40ab196ccf674056fed8b0e6d4f918eea183a149be8a67bff1239413ebada9",
        "face_sha256s": (
            # Bagel_Fat_One/BagelFatOne-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "9286944032c5a9b20ad70940105417beae14013e0b4f5fc292425afdc4330245",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Fredoka" / "OFL.txt"),
        "licence_evidence_sha256": "5c9e7eee5c6b25f4b05b8d53b2e470ea4962f9ced742d044a98f7d95d1375bab",
        "face_sha256s": (
            # Fredoka/Fredoka[wdth,wght].ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "2ba02e68b152868aef9ba28e24b3648c7d457fe6f25c761f2c2c53fb61a73fc8",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Chango" / "OFL.txt"),
        "licence_evidence_sha256": "e98ce988fba1c138f4e7c0c5120809706ab1b24a3c29638ca83ab2ff082e08db",
        "face_sha256s": (
            # Chango/Chango-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "3e566f4b881f24198fe1b6525aae970f9200078136e3416abc7ba0272d2f80d9",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Lalezar" / "OFL.txt"),
        "licence_evidence_sha256": "327bac41d89cf9f32e0efe353228018e1661cff458a5d4905714958514df7bd5",
        "face_sha256s": (
            # Lalezar/Lalezar-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "7b80807bc831f141de0f7dcf6816412bf0c548968d548c5156ca388733390ea9",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Reem_Kufi" / "OFL.txt"),
        "licence_evidence_sha256": "3e1dea8822e6e4008fe0ebd2f65f88579683cfee198c0089407fa197535dbe65",
        "face_sha256s": (
            # Reem_Kufi/ReemKufi[wght].ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "33ead1986cd48c138c4d906c9e5a6341877268461f97623409a2014de1cd4aa4",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Aref_Ruqaa" / "OFL.txt"),
        "licence_evidence_sha256": "41ac14451a624c69490e24b9aaaaa1f65dc9dc17c3f6f38172fc43d5ba654a1b",
        "face_sha256s": (
            # Aref_Ruqaa/ArefRuqaa-Bold.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "247071015b7eefd63f94d6e47949c5d10294ed31bd432f809ba9a219d93f91bb",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Aref_Ruqaa" / "OFL.txt"),
        "licence_evidence_sha256": "41ac14451a624c69490e24b9aaaaa1f65dc9dc17c3f6f38172fc43d5ba654a1b",
        "face_sha256s": (
            # Aref_Ruqaa/ArefRuqaa-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "ceb786d83ba92f35e96efcd8623c2858d288e0c543c8761ba35b1020989464f9",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Cairo_Variable" / "OFL.txt"),
        "licence_evidence_sha256": "a4554e1799d42e1405924b61eb0e0722ae1623b1f1f07f995348f96c496362a9",
        "face_sha256s": (
            # Cairo_Variable/Cairo[slnt,wght].ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "667c987182391c91f4e57a2f455b1794fb5e3ee6ca4ef3383e86bb690fa9c964",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Tajawal" / "OFL.txt"),
        "licence_evidence_sha256": "9b584984f9db0ee30347391a76eff9c0a6b03dc450c3c6afe3757a2cb3a4db87",
        "face_sha256s": (
            # Tajawal/Tajawal-Black.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "da582a579d3200869535dc994d2349608a8582042f8776b3679b157015db287c",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Tajawal" / "OFL.txt"),
        "licence_evidence_sha256": "9b584984f9db0ee30347391a76eff9c0a6b03dc450c3c6afe3757a2cb3a4db87",
        "face_sha256s": (
            # Tajawal/Tajawal-Bold.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "0342ab6b74b6bd1b4b5bf7beda45a9734a2b3147a31e8a3a45b6a3417a52d9d7",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Tajawal" / "OFL.txt"),
        "licence_evidence_sha256": "9b584984f9db0ee30347391a76eff9c0a6b03dc450c3c6afe3757a2cb3a4db87",
        "face_sha256s": (
            # Tajawal/Tajawal-ExtraBold.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "3d1298b747c22579f9e1bdeb0d4165064cb17f7e66145e2f43f9deb12ad7a2cf",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Tajawal" / "OFL.txt"),
        "licence_evidence_sha256": "9b584984f9db0ee30347391a76eff9c0a6b03dc450c3c6afe3757a2cb3a4db87",
        "face_sha256s": (
            # Tajawal/Tajawal-ExtraLight.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "a12ffbfaaec30ab8142edc60fa4727b104a90eb54c6a200a76988a1ec2ec11dc",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Tajawal" / "OFL.txt"),
        "licence_evidence_sha256": "9b584984f9db0ee30347391a76eff9c0a6b03dc450c3c6afe3757a2cb3a4db87",
        "face_sha256s": (
            # Tajawal/Tajawal-Light.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "ab26ed3e0c5af2c71b469b5780decff8088d290ab91aa29b07321580136e813a",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Tajawal" / "OFL.txt"),
        "licence_evidence_sha256": "9b584984f9db0ee30347391a76eff9c0a6b03dc450c3c6afe3757a2cb3a4db87",
        "face_sha256s": (
            # Tajawal/Tajawal-Medium.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "1ff8bd943a261c9dd7906bdb1993cab87b6d925a7fb5f848cdb51ed301531090",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-02",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Tajawal" / "OFL.txt"),
        "licence_evidence_sha256": "9b584984f9db0ee30347391a76eff9c0a6b03dc450c3c6afe3757a2cb3a4db87",
        "face_sha256s": (
            # Tajawal/Tajawal-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 9710da1)
            "6882892da3e03527d5db2bbab3b48bde6ef2e878a43f522d1a4eebda90010a19",
        ),
    },
)
#: [His goal of 2026-10-06, item 6 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a9ac953): "Approve Noto Naskh Arabic Bold
#: (SIL OFL, from google/fonts, licence and provenance recorded) for Arabic headings; no outline bolding."] The face is
#: google/fonts' NotoNaskhArabic[wght].ttf (commit 35ddfc5, version 2.021) at its wght 700 instance, made with fontTools
#: — google/fonts ships no static Bold; its licence is the OFL.txt beside it there, committed beside the face; how it was
#: made and every hash: docs/fonts/NotoNaskhArabic-Bold.provenance.json.
OWNER_GRANT_NASKH_BOLD = {
    "schema_version": SCHEMA,
    "granted_by": "BBrose",
    "granted_at": "2026-10-06",
    "licence_id": "SIL Open Font License, Version 1.1",
    "licence_evidence_path": str(Path(__file__).resolve().parents[2] / "static" / "fonts" /
                                 "NotoNaskhArabic-Bold.OFL.txt"),
    "licence_evidence_sha256": "a7a5a25eb188bf1cd96982030d53e23c33485c69b1044a562254226857ee13af",
    "face_sha256s": (
        # NotoNaskhArabic-Bold.ttf (google/fonts 35ddfc5 NotoNaskhArabic[wght].ttf at wght 700)
        "02ce983c927bc3198011535b84793f14e1755f40da6dfc5c02eb77920338fe29",
    ),
}
#: [His goal after the pitch page, 2026-10-15 (OWNER_BLOCKER_CLEARANCE.md), A (1): "Classify the concept's lettering
#: (serif / sans / script / condensed / display, weight, letter-spacing, case, colour) and set each line in the closest
#: granted face with the same weight, spacing, size and colour. Grant suitable OFL faces from google/fonts where none
#: fit (licence recorded), so every common style has a match."] The serif, condensed and geometric faces the set lacked,
#: granted §BH30(d)'s way — ONE ROW PER FACE keyed by its sha256, the OFL.txt that shipped beside it upstream pinned by
#: path and sha256; every sha256 measured from the bytes as fetched once from google/fonts (commit 67bc647) and recorded in
#: PROVENANCE.json; the evidence is re-hashed on every application.
OWNER_GRANTS_2026_10_15 = (
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "DM_Serif_Display" / "OFL.txt"),
        "licence_evidence_sha256": "a3e5cdd67d4571dd0a24fcc968de0efde7ae97ef752daf0906e4767619dd7231",
        "face_sha256s": (
            # DM_Serif_Display/DMSerifDisplay-Italic.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "df74c0ac387baeaeb0fe4f2324e1668e6a3ed8c09cd9796fe162c71753e19e45",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "DM_Serif_Display" / "OFL.txt"),
        "licence_evidence_sha256": "a3e5cdd67d4571dd0a24fcc968de0efde7ae97ef752daf0906e4767619dd7231",
        "face_sha256s": (
            # DM_Serif_Display/DMSerifDisplay-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "8cc3643535edf039aa5d95440a8542735e9197e4f4b8d9303e980fefbf5ab616",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Cormorant_Garamond" / "OFL.txt"),
        "licence_evidence_sha256": "60700d351cac4650c51f3f9db318d2a420f8b45052dba2715eb5fec41f0f6956",
        "face_sha256s": (
            # Cormorant_Garamond/CormorantGaramond-Italic[wght].ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "0f48ea6abb2084537854f7174c470991a463b13036309e3b50a81511611c530d",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Cormorant_Garamond" / "OFL.txt"),
        "licence_evidence_sha256": "60700d351cac4650c51f3f9db318d2a420f8b45052dba2715eb5fec41f0f6956",
        "face_sha256s": (
            # Cormorant_Garamond/CormorantGaramond[wght].ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "b20b7d9626dd956b2c5e558692ad328b1f19e3275e2782db4fa07670d83f35e0",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Libre_Baskerville" / "OFL.txt"),
        "licence_evidence_sha256": "3624eddd4c8f8a908130a417ae7cd089c9da69899c4e0ca1a5217d0a6fae16fd",
        "face_sha256s": (
            # Libre_Baskerville/LibreBaskerville-Italic[wght].ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "223959683dc73ec4437bd61fabaa4b3f22209e22855ffd3aee36ba61a5116e97",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Libre_Baskerville" / "OFL.txt"),
        "licence_evidence_sha256": "3624eddd4c8f8a908130a417ae7cd089c9da69899c4e0ca1a5217d0a6fae16fd",
        "face_sha256s": (
            # Libre_Baskerville/LibreBaskerville[wght].ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "05a95421961341c5b2556285e8415df9db27dab4f4abe22b446b3c6a8b916c5d",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Marcellus" / "OFL.txt"),
        "licence_evidence_sha256": "715ba72697e14daa9b29a333545f69bde7c497b9f77d0a2a4c4a5a752d961801",
        "face_sha256s": (
            # Marcellus/Marcellus-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "1cf0cd10b17d35e852729962cc1ffaffed94514895972458345e2df34abb2f81",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Italiana" / "OFL.txt"),
        "licence_evidence_sha256": "486c4d5b9baf0d0ba5546ef3c43fcfe22c062299ab6948045a43efffe4b0f74b",
        "face_sha256s": (
            # Italiana/Italiana-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "0ad271d9cd42a57cd5c5fa483ae2406a8138b95acb2a43eb73a8d37b7291fee9",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Abril_Fatface" / "OFL.txt"),
        "licence_evidence_sha256": "aba8997e16b1e3888c6e855ba883c70d96bd4375bff8cb9c7ce0f097200f74b8",
        "face_sha256s": (
            # Abril_Fatface/AbrilFatface-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "5971d4a3758a922a9fedc7f6fb825a96341a2e718c45a4b2c9a6b417c8c4dbe9",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Cinzel" / "OFL.txt"),
        "licence_evidence_sha256": "f2b3029aba64c378bf0963b62945eee15e564fe4330b934c8f2eb058282b5e83",
        "face_sha256s": (
            # Cinzel/Cinzel[wght].ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "f4d83d34d1f6c741193e4acf4b3dff9531e5a67b6aa65228d00a7db72a4e0f34",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Barlow_Condensed" / "OFL.txt"),
        "licence_evidence_sha256": "186d750eb496a4c17a76385f82be6aea2ac1cf2de074a811d63786cf374ea73f",
        "face_sha256s": (
            # Barlow_Condensed/BarlowCondensed-Bold.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "e476562ec9c1e16cf16475895b511f08c804f438cc9a9f80a44ea50a0eeb5b65",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Barlow_Condensed" / "OFL.txt"),
        "licence_evidence_sha256": "186d750eb496a4c17a76385f82be6aea2ac1cf2de074a811d63786cf374ea73f",
        "face_sha256s": (
            # Barlow_Condensed/BarlowCondensed-ExtraBold.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "724c9c25952d5f4a2d87185d9767aa006144c5f0d944dc05bf7d5d603551c260",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Barlow_Condensed" / "OFL.txt"),
        "licence_evidence_sha256": "186d750eb496a4c17a76385f82be6aea2ac1cf2de074a811d63786cf374ea73f",
        "face_sha256s": (
            # Barlow_Condensed/BarlowCondensed-Light.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "2c37e1e6b5feb71d38a42e6180d2e2f4ca1aad22cfecbd017430f3863deba67d",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Barlow_Condensed" / "OFL.txt"),
        "licence_evidence_sha256": "186d750eb496a4c17a76385f82be6aea2ac1cf2de074a811d63786cf374ea73f",
        "face_sha256s": (
            # Barlow_Condensed/BarlowCondensed-Medium.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "262bd143292ce479ee0cd09a42b47ab173fca8e9c6eb5ed0b5c8a845bc371d17",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Barlow_Condensed" / "OFL.txt"),
        "licence_evidence_sha256": "186d750eb496a4c17a76385f82be6aea2ac1cf2de074a811d63786cf374ea73f",
        "face_sha256s": (
            # Barlow_Condensed/BarlowCondensed-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "583cec5da3b84bc4dc7c9c72e2a565c94d34e431518b19d7e250b7830ad5f996",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Barlow_Condensed" / "OFL.txt"),
        "licence_evidence_sha256": "186d750eb496a4c17a76385f82be6aea2ac1cf2de074a811d63786cf374ea73f",
        "face_sha256s": (
            # Barlow_Condensed/BarlowCondensed-SemiBold.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "7b619d14bc2327509a9ef32b0890f709626f7ecc9ff61191c2a4314c5499d2d9",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Oswald" / "OFL.txt"),
        "licence_evidence_sha256": "0fd731a904b729a4e02eaf5e8ebd06783edd9abe400e8882760160230675b652",
        "face_sha256s": (
            # Oswald/Oswald[wght].ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "5b38c246e255a12f5712d640d56bcced0472466fc68983d2d0410ec0457c2817",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Jost" / "OFL.txt"),
        "licence_evidence_sha256": "1af3438a4d5f0ed2bdbc5751a5a67ebf6d537334161184b7fbb68503ef0ea0c5",
        "face_sha256s": (
            # Jost/Jost-Italic[wght].ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "15a6f7e3e11f9e8e338a583a6fe03e8f6b1d9ce877efa3fe579282b6c1cb15fe",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Jost" / "OFL.txt"),
        "licence_evidence_sha256": "1af3438a4d5f0ed2bdbc5751a5a67ebf6d537334161184b7fbb68503ef0ea0c5",
        "face_sha256s": (
            # Jost/Jost[wght].ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "6343b70971000b04c5d401c96ae08ce371086135e999d5e1e1413039c0213076",
        ),
    },
)
#: [His review of 127, 130, 131 and 132, 2026-10-15 (OWNER_BLOCKER_CLEARANCE.md), C (6): "130 and 132 a tall condensed
#: serif, at the concept's size"] the condensed serifs the set lacked, granted under his goal after the pitch page, A (1)
#: ("Grant suitable OFL faces from google/fonts where none fit (licence recorded)"), §BH30(d)'s way — one row per face,
#: its OFL.txt pinned; fetched once from google/fonts (commit 67bc647), recorded in PROVENANCE.json.
OWNER_GRANTS_2026_10_15_CONDENSED = (
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Instrument_Serif" / "OFL.txt"),
        "licence_evidence_sha256": "129ed7618959716959f2941fdd5b49e0ad6e6c1d78726761786a00253d865521",
        "face_sha256s": (
            # Instrument_Serif/InstrumentSerif-Italic.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "08939b8bdf534afec24ae0ef5e03f948940cd9a8fe08e7fecbad040e62327385",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Instrument_Serif" / "OFL.txt"),
        "licence_evidence_sha256": "129ed7618959716959f2941fdd5b49e0ad6e6c1d78726761786a00253d865521",
        "face_sha256s": (
            # Instrument_Serif/InstrumentSerif-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "498efd461f6ddfcb7a111bf9a565709d2085d48201d501ead960d93e84ffbb88",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-15",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Gloock" / "OFL.txt"),
        "licence_evidence_sha256": "321e28d45a430e017d9d1d6a47ef1fd261aad354723b014cf1933a765036c311",
        "face_sha256s": (
            # Gloock/Gloock-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "c3a67e0212f7da01764796ae721cb9bab3e122d142354f97cf9c63fb763e6d77",
        ),
    },
)
#: [his goal after the pitch page, B (10), 2026-10-16: the lotion tube's typewriter slab caption set in a bookish serif
#: for want of a slab] his grant of A (1) — "Grant suitable OFL faces from google/fonts where none fit (licence
#: recorded)" — the slab the set lacked
OWNER_GRANTS_2026_10_16_SLAB = (
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-16",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Courier_Prime" / "OFL.txt"),
        "licence_evidence_sha256": "9a755af092b494944c99f471be6fddd19b006a448fefdc4717e4ee0aa09a97b0",
        "face_sha256s": (
            # Courier_Prime/CourierPrime-Regular.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "72f793376f8e2841656bf21d77a5de010f2929bd6956a22ee848ad0c7eb978af",
        ),
    },
    {
        "schema_version": SCHEMA,
        "granted_by": "BBrose",
        "granted_at": "2026-10-16",
        "licence_id": "SIL Open Font License, Version 1.1",
        "licence_evidence_path": str(_BRAND2026 / "Courier_Prime" / "OFL.txt"),
        "licence_evidence_sha256": "9a755af092b494944c99f471be6fddd19b006a448fefdc4717e4ee0aa09a97b0",
        "face_sha256s": (
            # Courier_Prime/CourierPrime-Bold.ttf (ACQUIRED_UPSTREAM_RELEASE, google/fonts at 67bc647)
            "ff1f38786c849d1c41fa8e447960abdb2bd75fdfb0cfcdeb524fad65a5af3638",
        ),
    },
)
OWNER_GRANTS_BEFORE_DAY7 = ((OWNER_GRANT_BH26, OWNER_GRANT_NASKH) + OWNER_GRANTS_BH30 + OWNER_GRANTS_2026_10_02
                            + (OWNER_GRANT_NASKH_BOLD,) + OWNER_GRANTS_2026_10_15
                            + OWNER_GRANTS_2026_10_15_CONDENSED + OWNER_GRANTS_2026_10_16_SLAB)


def _day7_grants() -> tuple:
    """[D-D7-1, the owner's Day 7 prompt, 2026-10-19] the GRANTED pool of the materials library — 571 faces in 337 files,
    the Day 6 census (docs/audit/day-6/library/fonts-granted.json: each face's embedded licence wording) — granted for
    concepts and final artwork; one grant per licence wording, naming every file digest the earlier grants do not; the
    census file is the licence evidence, re-hashed on every application like every grant's. Built from the pool's catalogue
    record (apps/ire/font_pool.py); nothing where the record is absent."""
    from apps.ire import font_pool
    return font_pool.day7_grants()


OWNER_GRANTS = OWNER_GRANTS_BEFORE_DAY7 + _day7_grants()

_REQUIRED_FIELDS = ("granted_by", "granted_at", "licence_id",
                    "licence_evidence_path", "licence_evidence_sha256",
                    "face_sha256s")


def _measured_evidence_sha256(grant: dict) -> str | None:
    """Re-hash the licence file NOW. ``None`` when unreadable — leg (i)."""
    try:
        data = Path(grant["licence_evidence_path"]).read_bytes()
    except OSError:
        return None
    return hashlib.sha256(data).hexdigest()


def apply_owner_grant(authority: dict, *, grant: dict | None = None,
                      grants: tuple = None) -> dict:
    """Apply the owner grant to a ``container_font_authority/1.0`` record.

    Returns a NEW authority dict; the input is never mutated. Applied at the
    production call site AFTER ``build_font_authority`` and BEFORE
    ``font_confirmation_gate`` — never inside the builder, so the machine
    seam and every test that feeds it keep their meaning unchanged.

    ``all_production_verified`` is recomputed over the returned faces with
    the builder's own expression — measured, never forced.
    """
    # §BH30(d): a TUPLE of grants — `grant=` (one) keeps the §BH26 call shape;
    # `grants=` applies several; default = OWNER_GRANTS. For each face the FIRST
    # grant naming its sha256 governs (no sha256 is named twice — tested).
    if grant is not None:
        applied = (grant,)
    elif grants is not None:
        applied = tuple(grants)
    else:
        applied = OWNER_GRANTS
    # (iii) a malformed grant applies to nothing — dropped from the applied set.
    applied = tuple(g for g in applied if isinstance(g, dict)
                    and not any(not g.get(k) for k in _REQUIRED_FIELDS))
    faces = list(authority.get("faces") or [])
    if not faces or not applied:
        return dict(authority)

    # evidence re-hashed ONCE per application, per grant (leg (i))
    measured_by = {id(g): _measured_evidence_sha256(g) for g in applied}

    new_faces = []
    for face in faces:
        sha = (face or {}).get("sha256")
        grant = next((g for g in applied if sha in frozenset(g["face_sha256s"])), None)
        if grant is None:
            # (ii) the channel confers NOTHING on a face the grant does not
            # name — not even on the VOID path.
            new_faces.append(face)
            continue
        measured = measured_by[id(grant)]
        void = measured != grant["licence_evidence_sha256"]
        if void:
            # (i) grant VOID ⇒ fall back to LICENCE_REVIEW_REQUIRED, a
            # machine value through the machine guard. Only ``verification``
            # moves; no licence claim is written, no source flips.
            rec = dict(face)
            rec["verification"] = machine_writable_verification(
                LICENCE_REVIEW_REQUIRED)
            new_faces.append(rec)
            continue
        # The grant honored: owner-conferred states enter as OWNER DATA.
        src = SOURCE_USER_CONFIRMED
        rec = dict(face)
        rec.update({
            "verification": VERIFIED_FOR_PRODUCTION,
            "source": src,
            "licence_id": grant["licence_id"],
            "licence_evidence": (f'{grant["licence_evidence_path"]} '
                                 f'sha256:{measured}'),
            "redistribution_status": "GRANTED",
            "production_use_status": "GRANTED",
            "approved_by": grant["granted_by"],
            "approved_at": grant["granted_at"],
            # derived, not asserted — the _face_record expression.
            "is_fallback": src not in SOURCES_CLEARING_FALLBACK,
        })
        new_faces.append(rec)

    out = dict(authority)
    out["faces"] = new_faces
    out["all_production_verified"] = bool(new_faces) and all(
        r["verification"] == VERIFIED_FOR_PRODUCTION for r in new_faces)
    return out
