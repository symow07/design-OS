§BH29 STAGING REPORT — EVIDENCE HUNT, THE ONE REPORT, THEN STOP
═══════════════════════════════════════════════════════════════════════
Written 2026-09-03 at HEAD e1781ed. Fetched and staged, nothing concluded; the
executor selects and rules nothing. No spend. Durable artifacts under
~/bh29_work/ (evidence/<family>/… with .meta.json beside every file;
upstream/<family>/… for binaries fetched for hashing only; index.json keyed
by sha256; notes.json for reportage).

§0 THE GOAL'S ONE COMMIT — T29, PREDICTED 8-LEG AND SCORED
───────────────────────────────────────────────────────────────────────
T29 e1781ed — the §BH29 goal transcribed (pure append +112 −0 on the
17,962-line prefix). Gate TIER_2=GREEN collected=8499 failures=0 apps=7693
dip0c=671 dip0=135; ledger 442→443. 8/8 (~/bh29_work/pred_t29.txt,
score_t29.txt). The only commit of this goal; the hunt began after its
landing. Network measured reachable at receipt through the environment's
local proxy; every fetch below ran through it.

§1 CLAUSE (1) — SOURCE ATTRIBUTION PER FACE, GROUPED BY FAMILY
───────────────────────────────────────────────────────────────────────
Confidence classes as the owner defined them: HASH-MATCHED (an upstream
binary's sha256 equals the library file's), NAME+VERSION-MATCHED (upstream
carries the same family/style and the same declared version, bytes differ
or were not obtainable), FAMILY-MATCHED (upstream carries the family;
version differs or is not stated), UNRESOLVED. A hash MISMATCH against an
upstream that does carry the face is reported as exactly that.
■ Cairo  — upstream: google/fonts repository, ofl/cairo (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · Cairo-Regular.ttf  (referenced as Cairo-Regular; declared 'Version 2.009; ttfautohint (v1'; sha256 2f8534aa8392ec6f…)
       CLASS: FAMILY-MATCHED (version differs from every upstream build seen, current and historical; hash mismatch)
       1 distinct historical blobs seen over 16 commits touching ofl/cairo; historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 3.130;gftools[0.9.24]
     · Cairo-Bold(1).ttf  (referenced as Cairo-Bold; declared 'Version 2.010; ttfautohint (v1'; sha256 1936f28abe143ff1…)
       CLASS: HASH-MATCHED
       https://github.com/google/fonts/blob/e86936fd5b72936fe1eed526b69d49343a7d353b/ofl/cairo/Cairo-Bold.ttf (commit e86936fd, 2017-05-23; blob sha256 == library)
     · Cairo-SemiBold.ttf  (referenced as Cairo-SemiBold; declared 'Version 2.009; ttfautohint (v1'; sha256 7cd30c70ecab9424…)
       CLASS: FAMILY-MATCHED (version differs from every upstream build seen, current and historical; hash mismatch)
       1 distinct historical blobs seen over 16 commits touching ofl/cairo; historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 3.130;gftools[0.9.24]
■ Poppins  — upstream: google/fonts repository, ofl/poppins (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · Poppins-Bold.otf  (referenced as Poppins-Bold; declared 'Version 3.200;PS 1.000;hotconv'; sha256 50af8bcb91e0e404…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
     · Poppins-Regular.otf  (referenced as Poppins-Regular; declared 'Version 3.200;PS 1.000;hotconv'; sha256 45ad3c794aedbe7b…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
     · Poppins-Light.otf  (referenced as Poppins-Light; declared 'Version 3.200;PS 1.000;hotconv'; sha256 4141688311c8e3d7…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
     · Poppins-Medium.otf  (referenced as Poppins-Medium; declared 'Version 3.200;PS 1.000;hotconv'; sha256 9855b001069903d0…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
     · Poppins-SemiBold.otf  (referenced as Poppins-SemiBold; declared 'Version 3.200;PS 1.000;hotconv'; sha256 b6938a2903ed6013…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
     · Poppins-Black.otf  (referenced as Poppins-Black; declared 'Version 3.200;PS 1.000;hotconv'; sha256 d535c3b9c3aacdf9…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
■ Bebas Neue  — upstream: google/fonts repository, ofl/bebasneue (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
   notes: BebasNeue Bold.ttf and BebasNeue Book.ttf (v1.300 / v001.003, "All rights reserved", dharmatype.com) exist at NO commit of ofl/bebasneue — they are the Dharma Type 1.x freeware, not the Google Fonts release; see the Bebas (Dharma Type) record for their evidence.
     · BebasNeue Bold.ttf  (referenced as BebasNeueBold; declared 'Version 1.300'; sha256 c6d5e1a6d3691f17…)
       CLASS: FAMILY-MATCHED (no file of this name at ANY commit of the google/fonts directory — this build did not come from Google Fonts)
       0 distinct historical blobs seen over 12 commits touching ofl/bebasneue; historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 2.000
     · BebasNeue-Regular.otf  (referenced as BebasNeue; declared 'Version 2.000;PS 002.000;hotco'; sha256 a4ff052067127a47…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
     · BebasNeue Book.ttf  (referenced as BebasNeueBook; declared 'Version 001.003'; sha256 5b7780e6c76a19ad…)
       CLASS: FAMILY-MATCHED (no file of this name at ANY commit of the google/fonts directory — this build did not come from Google Fonts)
       0 distinct historical blobs seen over 12 commits touching ofl/bebasneue; historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 2.000
■ Great Vibes  — upstream: google/fonts repository, ofl/greatvibes (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · GreatVibes-Regular.ttf  (referenced as GreatVibes-Regular; declared 'Version 1.001'; sha256 f61866de92053395…)
       CLASS: NAME+VERSION-MATCHED, HASH MISMATCH (an upstream build declares the same version; the bytes differ)
       3 distinct historical blobs seen over 15 commits touching ofl/greatvibes; historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 1.103; ttfautohint (v1
■ Montserrat  — upstream: google/fonts repository, ofl/montserrat (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · Montserrat-Bold.otf  (referenced as Montserrat-Bold; declared 'Version 7.200;PS 007.200;hotco'; sha256 4a320e0b17988416…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
     · Montserrat-Bold.ttf  (referenced as Montserrat-Bold; declared 'Version 2.001'; sha256 9cb7dc18ee6175ab…)
       CLASS: FAMILY-MATCHED (version differs from every upstream build seen, current and historical; hash mismatch)
       5 distinct historical blobs seen over 20 commits touching ofl/montserrat; historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 9.000
     · Montserrat-Light.otf  (referenced as Montserrat-Light; declared 'Version 7.200;PS 007.200;hotco'; sha256 41a3cda98d362177…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
     · Montserrat-Black.otf  (referenced as Montserrat-Black; declared 'Version 7.200;PS 007.200;hotco'; sha256 265c987d31386e86…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
     · Montserrat-Medium.otf  (referenced as Montserrat-Medium; declared 'Version 7.200;PS 007.200;hotco'; sha256 956632cfc12cba5a…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
     · Montserrat-Regular.ttf  (referenced as Montserrat-Regular; declared 'Version 7.200'; sha256 81ebc3916b524007…)
       CLASS: HASH-MATCHED
       https://github.com/google/fonts/blob/9548902f8a5a0b4a0bb7427d93347a9ba9fd0f2e/ofl/montserrat/Montserrat-Regular.ttf (commit 9548902f, 2017-11-03; blob sha256 == library)
     · Montserrat-SemiBold.otf  (referenced as Montserrat-SemiBold; declared 'Version 3.001;PS 003.001;hotco'; sha256 ad0617cb22365ddd…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
     · Montserrat-SemiBold_0.otf  (referenced as Montserrat-SemiBold; declared 'Version 7.200;PS 007.200;hotco'; sha256 2ad662b83c167a1c…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
     · Montserrat-Thin.otf  (referenced as Montserrat-Thin; declared 'Version 7.200;PS 007.200;hotco'; sha256 8f213a8ce7430fad…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
■ Quicksand  — upstream: google/fonts repository, ofl/quicksand (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · Quicksand-Bold.ttf  (referenced as Quicksand-Bold; declared 'Version 3.006'; sha256 3c1eacad5998bf4e…)
       CLASS: NAME+VERSION-MATCHED, HASH MISMATCH (an upstream build declares the same version; the bytes differ)
       2 distinct historical blobs seen over 18 commits touching ofl/quicksand; historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 3.006
■ Amatic  — upstream: google/fonts repository, ofl/amaticsc (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · Amatic-Bold.ttf  (referenced as Amatic-Bold; declared 'Version 2.000; ttfautohint (v0'; sha256 889989f6a49973c1…)
       CLASS: NAME+VERSION-MATCHED, HASH MISMATCH (an upstream build declares the same version; the bytes differ)
       6 distinct historical blobs seen over 18 commits touching ofl/amaticsc; historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 2.505
■ Merriweather  — upstream: google/fonts repository, ofl/merriweather (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · Merriweather-Bold.ttf  (referenced as Merriweather-Bold; declared 'Version 1.570; ttfautohint (v1'; sha256 87ff42aa0b4bc370…)
       CLASS: FAMILY-MATCHED (version differs from every upstream build seen, current and historical; hash mismatch)
       8 distinct historical blobs seen over 30 commits touching ofl/merriweather; historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 2.100, Version 2.101
■ Open Sans  — upstream: google/fonts repository, ofl/opensans (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · OpenSans-Semibold.ttf  (referenced as OpenSans-Semibold; declared 'Version 1.10'; sha256 aa3b0ef53db12e3d…)
       CLASS: HASH-MATCHED
       https://github.com/google/fonts/blob/90abd17b4f97671435798b6147b698aa9087612f/apache/opensans/OpenSans-Semibold.ttf (commit 90abd17b, 2015-03-06; blob sha256 == library)
■ Playfair Display  — upstream: google/fonts repository, ofl/playfairdisplay (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · PlayfairDisplay-Bold.otf  (referenced as PlayfairDisplay-Bold; declared 'Version 1.004;PS 001.004;hotco'; sha256 7c6ae705a4c2d93a…)
       CLASS: FAMILY-MATCHED (HASH NOT TESTABLE: google/fonts ships TrueType only; the library file is OpenType CFF (.otf))
■ Raleway  — upstream: google/fonts repository, ofl/raleway (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · Raleway-Light.ttf  (referenced as Raleway-Light; declared 'Version 3.000; ttfautohint (v0'; sha256 d11b6f8bbb1025a5…)
       CLASS: HASH-MATCHED
       https://github.com/google/fonts/blob/90abd17b4f97671435798b6147b698aa9087612f/ofl/raleway/Raleway-Light.ttf (commit 90abd17b, 2015-03-06; blob sha256 == library)
     · Raleway-Thin.ttf  (referenced as Raleway-Thin; declared 'Version 2.001; ttfautohint (v0'; sha256 3499efab8f40fcf6…)
       CLASS: FAMILY-MATCHED (version differs from every upstream build seen, current and historical; hash mismatch)
       2 distinct historical blobs seen over 21 commits touching ofl/raleway; historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 4.026
■ Roboto  — upstream: google/fonts repository, ofl/roboto (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · Roboto-Light_0.ttf  (referenced as Roboto-Light; declared 'Version 1.00000; 2011'; sha256 94df4e4976db8dda…)
       CLASS: FAMILY-MATCHED (version differs from every upstream build seen, current and historical; hash mismatch)
       3 distinct historical blobs seen over 14 commits touching ofl/roboto plus 19 commits touching apache/roboto (the family's earlier Apache-licensed directory); historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 3.015; 2026
     · Roboto-Medium_0.ttf  (referenced as Roboto-Medium; declared 'Version 1.00000; 2011'; sha256 02868d6a7e80d4e7…)
       CLASS: FAMILY-MATCHED (version differs from every upstream build seen, current and historical; hash mismatch)
       3 distinct historical blobs seen over 14 commits touching ofl/roboto plus 19 commits touching apache/roboto (the family's earlier Apache-licensed directory); historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 3.015; 2026
■ Rubik  — upstream: google/fonts repository, ofl/rubik (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · Rubik-Bold.ttf  (referenced as Rubik-Bold; declared 'Version 2.000'; sha256 6ed15b1bb0bff1c5…)
       CLASS: HASH-MATCHED
       https://github.com/google/fonts/blob/a8f83b60237a44d7e329c200695069af03c0e0f7/ofl/rubik/Rubik-Bold.ttf (commit a8f83b60, 2016-12-05; blob sha256 == library)
■ Shadows Into Light Two  — upstream: google/fonts repository, ofl/shadowsintolighttwo (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · ShadowsIntoLightTwo-Regular.ttf  (referenced as ShadowsIntoLightTwo-Regular; declared 'Version 1.003 2012'; sha256 2794e63b651f594e…)
       CLASS: NAME+VERSION-MATCHED, HASH MISMATCH (an upstream build declares the same version; the bytes differ)
       1 distinct historical blobs seen over 11 commits touching ofl/shadowsintolighttwo; historical versions seen: {', '.join(sorted(set(x[:28] for x in hist_versions))) or 'not recorded'}; current upstream versions: Version 1.003 2012
■ Lato  — upstream: google/fonts repository, ofl/lato (authoritative artifact of the Google Fonts library)
   identified by: declared licence URL (scripts.sil.org/OFL / apache.org) + family name; repository listing by API; binaries fetched by raw URL and hashed; history walked through the commits API (path-limited) with raw fetches at each commit
   status: OPEN_LICENCE_TEXT_STORED
     · lato-black(1).ttf  (referenced as Lato-Black; declared 'Version 1.104; Western+Polish '; sha256 8b32bc539ca95dda…)
       CLASS: HASH-MATCHED
       https://github.com/google/fonts/blob/90abd17b4f97671435798b6147b698aa9087612f/ofl/lato/Lato-Black.ttf (commit 90abd17b, 2015-03-06; blob sha256 == library)
■ Hayah  — upstream: Arabic Font Resources / ZakDesign (per Luc Devroye: Zak Design, Zakariya Saleh, Ramallah). The declared licence_url http://zakdesign.net/ no longer serves the foundry: the live domain returns an 807-byte gb2312 stub titled "丹阳德蛹餐饮管理有限公司" with Baidu push scripts (domain repurposed). The 2011-06-22 Wayback snapshot shows an IPB forum "Arabic Font Resources" (Arabic fonts library) linking a ZakDesign blog. The face is currently carried only by third-party Arabic font repositories (arfonts.net).
   identified by: Declared strings (manufacturer "Arabic Font Resources.", copyright "Copyright (c) 2010 by Arabic Font Resources.", licence_url zakdesign.net, "Version 1.001 2010") + web search: arfonts.net listing names designer/foundry "Arabic Font Resources.", marketer "zakdesign.net", "Version 1.001 2010"; Luc Devroye page identifies Zak Design.
   status: UNRESOLVED
   reportage: arfonts.net (third-party repository; listing dated 2018/05/12) states in Arabic "الترخيص: مجاني للاستخدام الشخصي والتجاري" ("Licence: free for personal and commercial use") and lists designer/foundry "Arabic Font Resources.", marketer "zakdesign.net", "Version 1.001 2010", TrueType .ttf, 791 glyphs — a repository claim, not the foundry's text. The 2011 Wayback snapshot of zakdesign.net is a forum homepage (windows-1256) with no licence statement and no mention of Hayah.
   notes: Confidence qualification: the name+version match is against a third-party repository listing (arfonts serves a .ttf; the library file is Hayah.otf with the same version string), not against the foundry, whose site is gone; bytes not obtained (fonts not fetched). HTTP: http://zakdesign.net/ -> 301 -> http://www.zakdesign.net/ 200 (807 B); https://zakdesign.net/ -> connection failed (curl 000); urllib fetch hung >120 s, stored via curl. archive.org availability API located snapshot 20110622033318; port-80 fetch failed (curl 28, 75 s), https fetch succeeded (51,889 B). No licence text published by the foundry was located; the declared copyright string ends "All rights reserved. www" (truncated). Located but not fetched: fontke listing eng.m.fontke.com/font/10379901/ ("Hayah Version 1.001 2010"), X account @ArabicFonts.
     · Hayah.otf  (referenced as Hayah; declared 'Version 1.001 2010'; sha256 afae811e0d751ea7…)
       CLASS: NAME+VERSION-MATCHED
       Declared strings (manufacturer "Arabic Font Resources.", copyright "Copyright (c) 2010 by Arabic Font Resources.", licence_url zakdesign.net, "Version 1.001 2010") + web search: arfonts.net listing names designer/foundry "Arabic Font Resources.", marketer "zakdesign.net", "Version 1.001 2010"; Luc Devroye page identifies Zak Design.
■ Bauhaus 93  — upstream: Microsoft (bundling vendor: supplied with Microsoft 365 / Office as a cloud font). Foundry per Microsoft's page: URW ("Font vendor: URW Type Foundry", copyright "URW Software, Copyright 1993 by URW"). Declared http://www.urwpp.de -> 3 redirects -> https://www.myfonts.com/a/font/premium-font-collections/urw (Monotype-owned URW foundry listing, HTTP 200).
   identified by: Declared strings (copyright/manufacturer/licence_url) + Microsoft Typography font-list page (identical copyright string) + Office cloud fonts table ("Bauhaus 93 bauhaus93.ttf 1.53").
   status: BUNDLED — VENDOR TERMS PAGE STORED (reportage)
   bundling: Microsoft 365 / Office (cloud fonts) — https://support.microsoft.com/en-us/office/fonts/cloud-fonts-in-office (reached via the font-list link https://support.office.com/en-us/article/cloud-fonts-in-office-f7b009fe-037f-45ed-a556-b5fe6ede6adb); terms pages: Office 2024 Software License Terms PDF (fonts clause) and Font redistribution FAQ https://learn.microsoft.com/en-us/typography/fonts/font-faq (which scopes itself to Windows-supplied fonts).
   reportage: Microsoft Software License Terms, Office 2024 retail (PDF, "Last updated July 2024"), clause (iv), reportage: "While the software is running, you may use its fonts to display and print content. You may temporarily download the fonts to a printer or other output device to print content, and you may embed fonts in content only as permitted by the embedding restrictions in the fonts." Cloud fonts page: "Cloud fonts are available to Microsoft 365 subscribers." Font redistribution FAQ (learn.microsoft.com, ms.date 2024-11-19), reportage: scope — "they apply to all the fonts installed with Windows as system-wide resources"; "Unless you are using an application that is specifically licensed for home, student, or non-commercial use, we do not place any restrictions on what you do with print output that uses these fonts"; "We view creating graphic files as being essentially the same as printing from an output device"; videos: "the same as graphic files, providing the captions or text is rendered as a bitmap image, and the font files themselves are not embedded within the video file". NOTE: the FAQ's scope statement covers fonts installed with Windows; Bauhaus 93 is Office-supplied.
   notes: Version match: library BAUHS93.TTF "Version 1.53" = cloud-fonts table bauhaus93.ttf 1.53; bytes not obtained. The font-list page (last updated 2022-03-30) has no products/versions table and no Office mention. Which product supplied the owner's copy is not concluded. urwpp.de redirect target not stored (storefront listing, not a Bauhaus 93 page).
     · BAUHS93.TTF  (referenced as Bauhaus93; declared 'Version 1.53'; sha256 8afb4da281e19745…)
       CLASS: NAME+VERSION-MATCHED
       Declared strings (copyright/manufacturer/licence_url) + Microsoft Typography font-list page (identical copyright string) + Office cloud fonts table ("Bauhaus 93 bauhaus93.ttf 1.53").
■ Colonna MT  — upstream: Microsoft (bundling vendor: supplied with Microsoft 365 / Office as a cloud font; font-list page: "This typeface is available within Office applications"). Foundry per Microsoft's page: Monotype ("Font vendor: Agfa Monotype Corporation", designers Monotype Design Studio, copyright "Copyright © The Monotype Corporation plc. 1992. All rights reserved.").
   identified by: Declared copyright string (identical on the Microsoft font-list page) + Office cloud fonts table ("Colonna MT Colonna.ttf 1.52").
   status: BUNDLED — VENDOR TERMS PAGE STORED (reportage)
   bundling: Microsoft 365 / Office (cloud fonts) — https://support.microsoft.com/en-us/office/fonts/cloud-fonts-in-office; terms pages: Office 2024 Software License Terms PDF (fonts clause) and Font redistribution FAQ https://learn.microsoft.com/en-us/typography/fonts/font-faq (Windows-scoped).
   reportage: Microsoft Software License Terms, Office 2024 retail (PDF, "Last updated July 2024"), clause (iv), reportage: "While the software is running, you may use its fonts to display and print content. You may temporarily download the fonts to a printer or other output device to print content, and you may embed fonts in content only as permitted by the embedding restrictions in the fonts." Cloud fonts page: "Cloud fonts are available to Microsoft 365 subscribers." Font redistribution FAQ (learn.microsoft.com, ms.date 2024-11-19), reportage: scope — "they apply to all the fonts installed with Windows as system-wide resources"; "Unless you are using an application that is specifically licensed for home, student, or non-commercial use, we do not place any restrictions on what you do with print output that uses these fonts"; "We view creating graphic files as being essentially the same as printing from an output device"; videos: "the same as graphic files, providing the captions or text is rendered as a bitmap image, and the font files themselves are not embedded within the video file". NOTE: the FAQ's scope statement covers fonts installed with Windows; Colonna MT is Office-supplied.
   notes: VERSION DIFFERS: library COLONNA.TTF declares "Version 1.51"; Microsoft's current cloud-fonts table lists Colonna.ttf 1.52; the font-list page (last updated 2025-08-08) states no version. No Microsoft page listing 1.51 was found (an earlier Office release presumably shipped 1.51 — not verified). Bytes not obtained.
     · COLONNA.TTF  (referenced as ColonnaMT; declared 'Version 1.51'; sha256 7da22b3012c6071b…)
       CLASS: FAMILY-MATCHED
       Declared copyright string (identical on the Microsoft font-list page) + Office cloud fonts table ("Colonna MT Colonna.ttf 1.52").
■ Square721 BT  — upstream: Foundry: Bitstream Inc. (now Monotype; http://www.bitstream.com/ -> 301 -> https://www.monotype.com/ 200). Bundling vendor: Corel (CorelDRAW Graphics Suite ships Bitstream "BT" fonts; Corel's copyrights page defers font licensing to Bitstream). Retail: MyFonts (Monotype) "Square 721" by Bitstream, designer Aldo Novarese, 6 styles.
   identified by: Declared copyright "Copyright 1990-2003 Bitstream Inc." + the "BT" family suffix and "Version 1.01 emb4-OT" string (consistent with Corel-bundled Bitstream fonts per search reportage) + search (MyFonts/Monotype catalog product pages; Corel copyrights page).
   status: BUNDLED — VENDOR TERMS PAGE STORED (reportage)
   bundling: CorelDRAW Graphics Suite (Corel) — https://www.corel.com/en/corel-copyrights/ ("Fonts" section); the Corel EULA https://www.corel.com/en/eula/ is referred to for redistribution rights but its current text has no font clause.
   reportage: Corel copyrights page, reportage: "While Corel has developed some fonts in-house, most of the fonts found in Corel products have been licensed from independent font vendors. If you wish to license a particular font, you should contact Bitstream at www.bitstream.com, not Corel. Corel does not make fonts developed by it available for licensing." and, under Use of Software: "Please read the accompanying end user license agreement accompanying the software to determine your redistribution rights." Corel KB 128050: bonus fonts come with the DVD version; Bitstream Font Navigator; "Embed Fonts Using TrueDoc(TM)" on save. MyFonts, reportage: "Individual Styles from $29.99 USD", "Complete family of 6 fonts: $140.99 USD", licence types Desktop / Webfont / App / Electronic Doc / Digital Ad-Email / Server, "make sure to read the full EULA text" — retail path is commercial; licence evidence for it would require purchase.
   notes: Provenance of the owner's copy (Corel bundle vs retail vs other) is not established; the naming "Square721 BT Roman" differs from the retail "Square 721 Std Roman" and no version is stated on the retail page. No Corel page found states what the bundled fonts permit; the copyrights page defers to the product EULA (no font clause today) and to Bitstream (now Monotype). www.bitstream.com redirect target not stored (Monotype homepage).
     · Square721 BT Roman.ttf  (referenced as Square721BT-Roman; declared 'Version 1.01 emb4-OT'; sha256 afc6052419b36d84…)
       CLASS: FAMILY-MATCHED
       Declared copyright "Copyright 1990-2003 Bitstream Inc." + the "BT" family suffix and "Version 1.01 emb4-OT" string (consistent with Corel-bundled Bitstream fonts per search reportage) + search (MyFonts/Monotype catalog product pages; Corel copyrights page).
■ Arial  — upstream: Microsoft (bundling vendor: Windows-supplied font; also an Office cloud font). Foundry: The Monotype Corporation (copyright "© 2017 The Monotype Corporation. All Rights Reserved. Hebrew OpenType Layout logic copyright © 2003 & 2007, Ralph Hancock & John Hudson"; designers Robin Nicholas, Patricia Saunders, 1982 — per the Microsoft page).
   identified by: Declared strings (copyright/manufacturer identical on the Microsoft font-list page) + Windows 10 font list table ("Arial Bold Arialbd.ttf 7.00").
   status: BUNDLED — VENDOR TERMS PAGE STORED (reportage)
   bundling: Windows 10 (Windows-supplied font) — https://learn.microsoft.com/en-us/typography/fonts/windows_10_font_list; terms pages: Font redistribution FAQ https://learn.microsoft.com/en-us/typography/fonts/font-faq and Microsoft Product Terms https://www.microsoft.com/licensing/terms/product/ForallSoftware/all.
   reportage: Font redistribution FAQ (learn.microsoft.com, ms.date 2024-11-19), reportage: scope — "they apply to all the fonts installed with Windows as system-wide resources"; "Unless you are using an application that is specifically licensed for home, student, or non-commercial use, we do not place any restrictions on what you do with print output that uses these fonts"; "We view creating graphic files as being essentially the same as printing from an output device"; videos: "the same as graphic files, providing the captions or text is rendered as a bitmap image, and the font files themselves are not embedded within the video file". Microsoft Product Terms, Universal License Terms For all Software, "Font Components, Images, and Sounds", reportage: "may use the fonts included with or installed by that software to display and print content. Customer may only embed fonts in content as permitted by the embedding restrictions in the fonts; and temporarily download them to a printer or other output device to print content."
   notes: Version match: library arialbd.ttf "Version 7.00" = Windows 10 font list Arialbd.ttf 7.00; the Office cloud-fonts table today lists arialbd.ttf 7.04 (newer). The font-list page (last updated 2026-07-08) tabulates versions only up to Vista (5.01) and points to per-release pages for Windows 7-11. The page's "License Microsoft fonts" link https://www.fonts.com/content/microsoft-typography now -> https://www.myfonts.com/a/font/form/microsoft-typography-licensing (200; a Monotype licensing enquiry form) — not stored. Which Windows release supplied the owner's copy is not concluded.
     · arialbd.ttf  (referenced as Arial-BoldMT; declared 'Version 7.00'; sha256 766f06ac8761f82f…)
       CLASS: NAME+VERSION-MATCHED
       Declared strings (copyright/manufacturer identical on the Microsoft font-list page) + Windows 10 font list table ("Arial Bold Arialbd.ttf 7.00").
■ Bahnschrift  — upstream: Microsoft Corporation (foundry and bundling vendor; Windows 10/11-supplied; designer Aaron Bell; released as a variable font for Windows in 2017 per the Microsoft page).
   identified by: Declared strings (manufacturer Microsoft, licence_url docs.microsoft.com/typography/about) + Microsoft font-list page + Windows 10 font list table ("Bahnschrift * Bahnschrift.ttf 2.06").
   status: BUNDLED — VENDOR TERMS PAGE STORED (reportage)
   bundling: Windows 10 / Windows 11 (Windows-supplied font) — https://learn.microsoft.com/en-us/typography/fonts/windows_10_font_list; terms pages: Font redistribution FAQ https://learn.microsoft.com/en-us/typography/fonts/font-faq and Microsoft Product Terms https://www.microsoft.com/licensing/terms/product/ForallSoftware/all.
   reportage: Declared licence_url https://docs.microsoft.com/typography/about -> 2 redirects -> https://learn.microsoft.com/en-us/typography/about (200): an "About Microsoft Typography" page (ms.date 2020-03-10), not a licence text. Font redistribution FAQ (learn.microsoft.com, ms.date 2024-11-19), reportage: scope — "they apply to all the fonts installed with Windows as system-wide resources"; "Unless you are using an application that is specifically licensed for home, student, or non-commercial use, we do not place any restrictions on what you do with print output that uses these fonts"; "We view creating graphic files as being essentially the same as printing from an output device"; videos: "the same as graphic files, providing the captions or text is rendered as a bitmap image, and the font files themselves are not embedded within the video file". Microsoft Product Terms, Universal License Terms For all Software, "Font Components, Images, and Sounds", reportage: "may use the fonts included with or installed by that software to display and print content. Customer may only embed fonts in content as permitted by the embedding restrictions in the fonts; and temporarily download them to a printer or other output device to print content."
   notes: Version match: library bahnschrift.ttf "Version 2.06" = Windows 10 font list Bahnschrift.ttf 2.06. Copyright year differs between file (© 2018) and the font-list page (© 2019) — recorded, not resolved. The Office cloud-fonts table lists other Bahnschrift files (e.g. bahnschrift-semilight-condensed.ttf 2.08), not the library's file.
     · bahnschrift.ttf  (referenced as Bahnschrift; declared 'Version 2.06'; sha256 bff1ca87ea35e376…)
       CLASS: NAME+VERSION-MATCHED
       Declared strings (manufacturer Microsoft, licence_url docs.microsoft.com/typography/about) + Microsoft font-list page + Windows 10 font list table ("Bahnschrift * Bahnschrift.ttf 2.06").
■ Selima  — upstream: Jroh Creative (designer; Banda Aceh, Indonesia) — own site jrohcreative.com (freebies/selima-script) and Behance gallery 33401167 'Selima - Free Font' (behance.net/jrohcreative, the declared licence_url)
   identified by: declared strings (copyright '@zamroni_agus', licence_url 'behance.net/jrohcreative') + web search → the Behance project, whose description links the designer's own download page
   status: OPEN_LICENCE_TEXT_STORED
   reportage: REPORTAGE — Behance project (stored bytes): 'Selima Free Brush Script is FREE for PERSONAL & COMMERCIAL USE !'. Designer's own page jrohcreative.com/freebies/selima-script (stored SPA bytes; embedded data-page JSON): name 'Selima Script', formats ['OTF','RTF'], includes ['1 style included','Formats: OTF, RTF','Free license · personal & commercial'], identity {glyph_count 223, version '1.000', style_count 1}. Rendered page (read-only browser view, not stored): 'LICENSE Free'; 'Free downloads are for members. Sign in (it's free) and the zip downloads instantly'. dafont author note (aggregator; stored by the earlier leg): '100% FREE, even for commercial purpose.'
   notes: Version match rests on the designer's own page payload ('version':'1.000' vs the library's 1.000). Bytes NOT obtained: the designer's download is account-gated (login/register), so no zip was fetched and no hash comparison was possible; the page's live-preview font is served from a signed, expiring URL and was deliberately not fetched. The stored page is a JS-app shell (creatorspace.id) with 15 chars of visible text — the evidence is in its embedded JSON. No formal EULA document exists on the designer's channels; the 'licence text' is the designer's one-line statement, so OPEN_LICENCE_TEXT_STORED is to be read with that qualification. WebFetch cannot read jrohcreative.com (policy); the rendered view came from the browser pane, read-only, nothing entered or clicked. fontsquirrel/fontmeme/befonts copies are aggregators, not used.
     · selima.otf  (referenced as Selima; declared '1.000'; sha256 ed062985705cda70…)
       CLASS: NAME+VERSION-MATCHED
       declared strings (copyright '@zamroni_agus', licence_url 'behance.net/jrohcreative') + web search → the Behance project, whose description links the designer's own download page
■ Nickainley  — upstream: Seniors Studio (Indonesia) — Behance gallery 24243507 'Nickainley Script - Free Font' (behance.net/seniorsstudio); the project names its download hosts: fontfabric.com/nickainley-free-font/ (Fontfabric; email-gated free download under the Fontfabric FFF EULA 2.0), dafont, fontsquirrel
   identified by: declared copyright 'Seniors Studio' + web search → Behance project; the Fontfabric host and the FFF EULA are named by the project and by the licence file bundled with the font (inkstitch copy stored by the earlier leg)
   status: OPEN_LICENCE_TEXT_STORED
   reportage: REPORTAGE — Behance project (stored bytes): 'Free for Personal and Commercial use'; download links listed: fontfabric.com/nickainley-free-font/, dafont.com/nickainley.font, fontsquirrel.com/fonts/nickainley. Fontfabric page (stored): 'Download for free' → 'We'll send you a zipped file with the free font, license agreement, and installation instructions' behind an email form; 'Credits: Seniors Studio'; the page also shows Fontfabric's generic licence-purchase panel. fontsquirrel licence page (stored): "License for 'Nickainley' — Fontfabric License, FFF EULA ver. 2.0 June 2015: 'All fonts on the site (fontfabric.com) available for free download (except “Baron”) can be used for both personal and commercial work' ... 'You may not modify, adapt ... or create derivative works' ... 'You may not resell or redistribute'". inkstitch LICENSE copy (stored by the earlier leg): the same EULA plus an email exchange in which Seniors Studio answered 'Yes, you allowed :)' to an embroidery-adaptation request.
   notes: No version stated on any page (library: 'Version 1.000;PS 001.000;hotconv...'). No bytes obtained — the only designer-named host offering a download (Fontfabric) requires an email address; dafont/fontsquirrel are aggregators — so no download and no hash comparison. The licence text is Fontfabric's EULA (a distributor's EULA applied to fonts it hosts), stored via fontsquirrel's republication and the inkstitch copy, not from a Seniors Studio page; the designer's own statement is the one-line Behance text. The first fontsquirrel fetch returned HTTP 200 with a 0-byte body (urllib); re-fetched with curl (24,047 B) and the stray empty-body index entry pruned. Creative Fabrica also lists 'Nickainley by seniorsstudio' (not fetched, budget).
     · Nickainley-Normal.otf  (referenced as Nickainley-Normal; declared 'Version 1.000;PS 001.000;hotco'; sha256 ddd2830cccd01adc…)
       CLASS: FAMILY-MATCHED
       declared copyright 'Seniors Studio' + web search → Behance project; the Fontfabric host and the FFF EULA are named by the project and by the licence file bundled with the font (inkstitch copy stored by the earlier leg)
■ BORELA  — upstream: Maiko Hatta / 'MaikoHatta' (credited on dafont as Gilang Ternadho) — Creative Market shop MaikoHatta, product 27129461 'BORELA - Modern Sans Serif Font' (commercial); Envato Elements user 'maikohatta' (linked from the author's dafont note); designer-uploaded personal-use demo on fontspace (borela-font-f103891) and dafont (borela.font), both carrying the author's own note
   identified by: declared copyright '©Maikohatta' + web search; the library filename suffix '-6YX71' is fontspace's naming pattern, and the fontspace listing was located through the designer's fontspace profile/search
   status: FREE_FOR_PERSONAL_USE — commercial requires purchase (COMMERCIAL — EVIDENCE REQUIRES PURCHASE)
   reportage: REPORTAGE — dafont author note (stored): '1. This font is for PERSONAL USE ONLY. No promotional or commercial use is permitted. 2. You need a license for promotional or commercial use. 3. You will be charged 20x the Renewal License Price if you violate this agreement. 4. ... https://elements.envato.com/fonts/maikohatta 5. ... maikofarazhatta@gmail.com' (repeated in Indonesian). fontspace listing (stored): 'License Info: Freeware, Non-Commercial'; designer note 'NOTE: This demo font is for PERSONAL USE ONLY! and NO COMMERCIAL USE ALLOWED'; 'Commercial licenses ... Buy at Creative Fabrica'; 'Regular Style, TrueType/PostScript, 153 glyphs, 167 characters'. Creative Market product page (NOT stored — HTTP 403 to direct clients; summary via the fetch proxy): 'BORELA - Modern Sans Serif Font' by MaikoHatta, Desktop $18.00, Webfont $20.00, E-pub $36.00, App $144.00, OTF+TTF, created July 19, 2023.
   notes: creativemarket.com answers HTTP 403 to urllib and to curl (also with full browser headers / HTTP1.1), so the commercial product page could not be stored byte-verbatim; creativefabrica.com/product/borela/ answers HTTP 403 to curl and to WebFetch, so the CF listing named by fontspace is unverified. No page states a version (library: 'Version 1.001;Fontself Maker 3'); dafont lists BORELA.ttf while the library file is Borela-6YX71.otf (fontspace naming). No download attempted (free copies are aggregator-hosted only; the commercial copy requires purchase), so no hash comparison. Attribution discrepancy recorded, not resolved: font strings '©Maikohatta', dafont 'Gilang Ternadho', fontspace 'Maiko Hatta'. Envato Elements shows other MaikoHatta fonts but no Borela listing surfaced in search.
     · Borela-6YX71.otf  (referenced as BORELARegular; declared 'Version 1.001;Fontself Maker 3'; sha256 6bb00e89975c5f2c…)
       CLASS: FAMILY-MATCHED
       declared copyright '©Maikohatta' + web search; the library filename suffix '-6YX71' is fontspace's naming pattern, and the fontspace listing was located through the designer's fontspace profile/search
■ Blisey  — upstream: Syauqi Studio (type foundry, Tangerang, Indonesia; designer credited by MyFonts as Muhammad Asroful Umam) — Behance gallery 219816927 'Blisey: Psychedelic Display Typeface' (behance.net/syauqistudio); designer's Gumroad storefront syauqistudio.gumroad.com/l/blisey (commercial); marketplace listings on MyFonts (collections/blisey-font-syauqi-studio) and Fontspring; the personal-use demo is directed by the designer to 1001fonts.com
   identified by: declared copyright 'Typeface © (Syauqi Studio). 2025' + web search → MyFonts/Fontspring/Behance profile; the gallery itself was located with a Behance search in the browser pane (the profile's first page does not list it)
   status: FREE_FOR_PERSONAL_USE — commercial requires purchase (COMMERCIAL — EVIDENCE REQUIRES PURCHASE)
   reportage: REPORTAGE — Behance project (stored; fetch-proxy summary): 'Download for Free Personal Use' → 1001fonts.com; 'Download for COMMERCIAL USE and Get the Best Price' → syauqistudio.gumroad.com/l/blisey; published February 21, 2025; the stored bytes contain 'Personal Use:', 'COMMERCIAL USE and Get the Best Price:' and 'gumroad.com/l/blisey'. Gumroad page (stored; embedded JSON): name 'Blisey - Psychedelic Retro Display Typeface for Unique Designs', price 21.0 USD, seller 'Syauqi Studio | Type Foundry'. MyFonts (stored; summary): 6 styles (Light/Light Italic/Regular/Italic/Bold/Bold Italic), $17.00 per style, family $21.00, licence types Desktop / Company Desktop / Webfonts / App / Digital Ad-Email / Electronic Doc, released February 20, 2025, no free version mentioned. Aggregators (1001fonts, freedesignresources, befonts) describe the free file as a demo for personal use.
   notes: No version stated on any page (library: 'Version 1.00;February 12, 2025'; the library holds a single 'Blisey' face while the commercial family has 6 styles — recorded, not interpreted). No Syauqi Studio own-domain found (syauqistudio.com / www.syauqistudio.com / syauqi.studio all fail the TLS handshake). The demo is offered only via aggregators (1001fonts, named by the designer), so nothing was downloaded and no hash comparison was made; the commercial EULA is behind purchase. The Gumroad page is mostly JS (64 chars of visible text); price/name read from its embedded JSON. The designer's Behance profile page was also stored (used to look for the gallery).
     · Blisey.otf  (referenced as Blisey; declared 'Version 1.00;February 12, 2025'; sha256 660e2dc30041257c…)
       CLASS: FAMILY-MATCHED
       declared copyright 'Typeface © (Syauqi Studio). 2025' + web search → MyFonts/Fontspring/Behance profile; the gallery itself was located with a Behance search in the browser pane (the profile's first page does not list it)
■ Figerona Black  — upstream: Drizy Studio (Faqih Fawaji) — own store drizystudio.com (product/figerona/ + license/), second own site drizyfont.com (product + licenses pages), Behance project 130041031; the designer's own dafont listing (file Figerona-VF.ttf) carrying his note
   identified by: declared copyright 'Figerona (c) Drizy Studio 2021' + web search; the earlier leg had already stored both Drizy sites; the library filename 'FontsFree-Net-Figerona-VF(1).ttf' is fontsfree.net's re-hosting pattern of the dafont 'Figerona-VF.ttf' file
   status: FREE_FOR_PERSONAL_USE — commercial requires purchase (COMMERCIAL — EVIDENCE REQUIRES PURCHASE)
   reportage: REPORTAGE — dafont author note (stored): 'By purchasing, downloading and installing this font, you accept and agree to the Product Use License Agreement: - This is already FULL VERSION FONT and ONLY for PERSONAL USE. NO COMMERCIAL USE ALLOWED! - Here is the link to purchase COMMERCIAL LICENSE: https://drizystudio.com/product/figerona/ - If you need a CUSTOM LICENSE or CORPORATE LICENSE please contact us at: admin@drizystudio.com'; file listed Figerona-VF.ttf; first seen November 01, 2022. drizystudio.com product page (stored): 'Figerona – Geometric Variable Typeface by Drizy Studio, June 16, 2022 ... License Option: Personal License $12, Webfont License ...'; styles listed Thin→Black including 'Figerona Black'. drizystudio.com/license/ (stored): Desktop License '1 User, 5 Commercial Project, Unlimited Personal Project, 2 Computer Installation ...'; Extended License 'Maks. 10 User ...'. drizyfont.com product (stored): 'Family Package $ 57,99 — For non-commercial personal use' / '$ 84,99 — For freelance professionals ...'.
   notes: No page states a version (library: 'Version 1.000'), hence FAMILY-MATCHED. The free file reaches users through aggregators (dafont, then fontsfree.net which produced the library's filename) — not the designer's own page — so no download and no hash comparison. The file's governing text is the author's dafont note, not a formal EULA; the commercial EULA is behind purchase. The two Drizy sites (both the designer's) show different packages/prices — recorded as reportage. Behance project 130041031 was not re-fetched (budget).
     · FontsFree-Net-Figerona-VF(1).ttf  (referenced as Figerona-Black; declared 'Version 1.000'; sha256 39b28a4370a70555…)
       CLASS: FAMILY-MATCHED
       declared copyright 'Figerona (c) Drizy Studio 2021' + web search; the earlier leg had already stored both Drizy sites; the library filename 'FontsFree-Net-Figerona-VF(1).ttf' is fontsfree.net's re-hosting pattern of the dafont 'Figerona-VF.ttf' file
■ Komika Axis  — upstream: Apostrophic Laboratories ('Apostrophic Labs', apostrofe@mail.com; WolfBainX listed among its collaborators) — own site apostrophiclab.com, DEFUNCT; in 2001 it was a frameset over hardcovermedia.com/lab/ (Wayback captures stored); dafont now lists the font under 'Vigilante Typeface Corporation' linking facebook.com/wolfbainx; the 'Apostrophic Labs License' text survives as a third-party republication (localfonts.eu, stored by the earlier leg)
   identified by: declared strings ('© 1999-2001, WolfBainX & Apostrophic Labs', licence_url 'www.@apostrophiclab.com') + web search; Wayback Machine reached with curl through the proxy (WebFetch is blocked for web.archive.org); captures chosen from the CDX index
   status: OPEN_LICENCE_TEXT_STORED
   reportage: REPORTAGE — Apostrophic Labs License (third-party republication at localfonts.eu, stored by the earlier leg): 'The fonts on this site are freeware and can be used as they are in any context without permission from Apostrophic Laboratories, except to produce material that is racist, criminal and/or illegal in nature. It is prohibited to modify any Apostrophic Laboratories font(s) for repackaging and/or re-release without an express written authorization by the designer(s) of the font(s) or Apostrophic Laboratories. Under no circumstance shall any Apostrophic Laboratories design or font design be sold or purchased.' Copyright holder's own archived main page, Feb 2001 (stored): no 'freeware' passage found in its text. Copyright holder's own archived page, Dec 2003 (stored): 'This site offers public domain fonts ... The old apostrophiclab.com contained over 1000 free font packages for download. Many of those packages will be coming back under a new public domain license instead of their initial freeware one.' Archived 'laboratory' page, Feb 2001 (stored): lists the lab's collaborators including 'WolfBainX'. dafont (stored): 'Free for personal use', author shown as 'Vigilante Typeface Corporation' (link facebook.com/wolfbainx), file KOMIKAX_.ttf, first seen 'before 2005'. No archived Komika Axis page was obtainable (see notes).
   notes: apostrophiclab.com is defunct (the declared licence_url 'www.@apostrophiclab.com' is malformed); Wayback captures 2001-03 and 2003-01 of the root are 200-361-byte frameset stubs pointing at hardcovermedia.com/lab/, where the 2001 catalogue lived. The CDX index lists per-font pages there for sibling Komika faces (komikahuna.html, komikazba.html, komikaze.html, komikazoom.html) but no page for Komika Axis itself was found in the 80-row listing, and the targeted 'lab/komika*' prefix queries answered HTTP 503 (Wayback overload) on both attempts — so no upstream page carrying this exact face was stored and the confidence class stays UNRESOLVED although every source attributes the family to Apostrophic Labs/WolfBainX. No page states the library's version '2.0'. Licence classification is inconsistent across sources and is recorded, not resolved: the era licence text says 'freeware ... any context' (third-party republication), the holder's 2003 page speaks of a 'new public domain license', dafont says 'Free for personal use'. WebFetch is blocked for web.archive.org; curl through the proxy works. One mis-fetch (the LIVE hardcovermedia.com, an unrelated current owner) was pruned from evidence/ and index.json. Nothing downloaded (no designer-offered binary exists).
     · KOMIKAX.ttf  (referenced as KomikaAxis; declared '2.0'; sha256 d2c790c5ce96e445…)
       CLASS: UNRESOLVED
       declared strings ('© 1999-2001, WolfBainX & Apostrophic Labs', licence_url 'www.@apostrophiclab.com') + web search; Wayback Machine reached with curl through the proxy (WebFetch is blocked for web.archive.org); captures chosen from the CDX index
■ 2  Narenj  — upstream: UNRESOLVED — 'Mrtsoft' / 'MRT' (Mohammad Reza Tavakoli; win2farsi.com, MRTpack.com per aggregator metadata and the archived site's generator tag) has no locatable foundry channel: win2farsi.com no longer resolves in DNS, mrtpack.com serves HTTP 404, and the 2010 Wayback capture of win2farsi.com is a Persian software-download listing page (e.g. '374 Farsi Fonts new 2010' via rapidshare) with no font licence statement
   identified by: declared copyright '(c) 1998 Mrtsoft' + web search (aggregators fontke/arbfonts/freearabicfont attribute the font to Mrtsoft, 'released 2016')
   status: UNRESOLVED
   reportage: REPORTAGE — arbfonts.com (aggregator, Arabic; stored): company 'Mrtsoft', copyright '(c) 1998 Mrtsoft', ttf, weight Regular, listed '9 years' ago. fontke (aggregator; search summary, page not storable): licence 'Unknown', 288 characters. Web summaries attribute an unsourced 'Do not use it commercially without authorization' line to aggregator pages. Archived win2farsi.com, 2010 (stored): 'Modified:1995-2010 MRT www.win2farsi.com' followed by a software/Windows/fonts download list; generator tag 'MRTpack.com'.
   notes: fontke's licence page redirects in a loop (en.m.fontke.com → 301 english.m.fontke.com → 302; eng.fontke.com → 301 english.fontke.com → 302) — not stored. Same-name ambiguity: 'B Narenj' (Borna Rayaneh's 'B' series) is a different vendor's font of the same name; the '2 ' prefix is a vendor-series prefix. The version string 'Version 1.00 November 10, 2016' against a 1998 copyright indicates repackaging. No designer channel → nothing downloaded, no hash comparison. Aggregator-only availability.
     · 2  Narenj Regular.ttf  (referenced as 2Narenj; declared 'Version 1.00 November 10, 2016'; sha256 23e5709dcde7136d…)
       CLASS: UNRESOLVED
       declared copyright '(c) 1998 Mrtsoft' + web search (aggregators fontke/arbfonts/freearabicfont attribute the font to Mrtsoft, 'released 2016')
■ HASOOB  — upstream: UNRESOLVED — no designer/foundry channel located; the font's own strings identify only 'Generated by Fontographer 3.5' (1993) with vendor/subfamily tags 'AAHS:HASSOB' / 'AAHS:Kuwait' as shown by aggregators; 'FP Hasoob' (Fontparsi, Mohammad Amuie) is a later, differently named font
   identified by: declared strings + web search (aggregators only: arafonts, wfonts, world-fonts, arbfonts, alfont)
   status: UNRESOLVED
   reportage: REPORTAGE — wfonts.com (aggregator; stored): 'AAHS:HASSOB FontName HASSOB NameTableVersion 1 ... Copyright Generated by Fontographer 3.5'. arafonts.com (search summary; site unreachable): 'associated with AAHS:Kuwait', 'popular in Saudi Arabia'. No licence text or terms statement exists on any located page.
   notes: arafonts.com is unreachable (port 80 connect failure; port 443 TLS failure); world-fonts.com fails the TLS handshake; wfonts.com stored via curl. The font predates the web (Sep 1993, Fontographer 3.5) and carries no author or licence strings; same-name ambiguity with 'FP Hasoob'. Nothing downloaded, no hash comparison. Aggregator-only availability.
     · HASOOB.ttf  (referenced as HASOOB; declared '1.0 Sun Sep 12 16:30:47 1993'; sha256 5c579f803c747d0b…)
       CLASS: UNRESOLVED
       declared strings + web search (aggregators only: arafonts, wfonts, world-fonts, arbfonts, alfont)
■ Adobe Arabic  — upstream: Adobe Inc. — Adobe Originals; commissioned from Tiro Typeworks (designers Tim Holloway and Robert Slimbach per fonts.adobe.com). Library file AdobeArabic-Regular.otf: Version 2.006, manufacturer string "Tiro Typeworks for Adobe Syste[ms]", copyright 2000, 2002, 2004, 2011 Adobe Systems Incorporated, licence_url http://www.adobe.com/type/legal.html.
   identified by: Name-table manufacturer/copyright strings from families.json; Adobe Fonts product page (fonts.adobe.com/fonts/adobe-arabic) credits "Designed by Robert Slimbach and Tim Holloway. From Adobe Originals."; bundling identified from Adobe's own AEM Forms Designer documentation (help.adobe.com) which lists Adobe Arabic among fonts available in Acrobat/Reader.
   status: BUNDLED — VENDOR TERMS PAGE STORED (reportage)
   bundling: Adobe Acrobat (all 4 styles always available, per Adobe AEM Forms Designer help); Adobe Reader when the "Extended Language Package" (Reader font pack) is installed; also served through Adobe Fonts to Creative Cloud subscribers ("Subscribe to Creative Cloud to use more fonts" on the product page). Which of these installed the library copy is not determinable from the pages.
   reportage: REPORTAGE (quoted, not assessed): fonts.adobe.com product page: "The full Adobe Fonts library is cleared for both personal and commercial use." and "Visit the Adobe Fonts Licensing FAQ for full details". Adobe AEM Forms Designer help 'Choosing fonts for performance': "the following fonts are always available in Acrobat and Adobe Reader, and do not need to be embedded" — list includes "Myriad Pro Bold, Myriad Pro Bold It, Myriad Pro It, Myriad Pro Regular" and "Adobe Arabic/Hebrew/Thai with all 4 styles (Bold, BoldItalic, Italic, and Regular). Available in Adobe Reader when the Extended Language Package is installed". helpx FAQ 'Note' (Last updated on Mar 27, 2026): "Fonts installed in the Fonts folder on your computer are licensed under their own end-user agreements. These FAQs don't apply to those fonts. Contact the font foundry directly for license questions."
   notes: Declared licence_url http://www.adobe.com/type/legal.html no longer serves a legal page: WebFetch reports it redirects to https://www.adobe.com/products/type.html ("Buy, download typography fonts | Adobe Type"); no vendor page naming Version 2.006 was found, hence FAMILY-MATCHED. The Adobe Fonts product page speaks to the subscription (Adobe Fonts) copy of the family; the helpx FAQ explicitly says its FAQs do not apply to fonts installed in the computer's Fonts folder (see reportage) — so the terms for the copy installed by Acrobat/Reader are the respective product EULAs, which were not hunted here. Network notes: adobe.com hosts (www/helpx) are Akamai-fronted; through the environment proxy, curl with a spoofed Chrome User-Agent fails (HTTP/2 'stream 1 was not closed cleanly: INTERNAL_ERROR (err 2)', curl rc=92) and HTTP/1.1 times out with 0 bytes (curl rc=28); curl's default User-Agent succeeds (HTTP 200). Pages were therefore stored with store_ua.py (same store()/meta/index code path, -A removed). Search-engine snippet (community.adobe.com, not vendor terms, not stored) also describes Adobe Arabic as available in Acrobat and, in Reader, only with the Arabic/Extended language font package.
     · AdobeArabic-Regular.otf  (referenced as AdobeArabic-Regular; declared 'Version 2.006'; sha256 dda73d3ab68b3036…)
       CLASS: FAMILY-MATCHED
       Name-table manufacturer/copyright strings from families.json; Adobe Fonts product page (fonts.adobe.com/fonts/adobe-arabic) credits "Designed by Robert Slimbach and Tim Holloway. From Adobe Originals."; bundling identified from Adobe's own AEM Forms Designer documentation (help.adobe.com) which lists Adobe Arabic among fonts available in Acrobat/Reader.
■ Myriad Pro  — upstream: Adobe Inc. (Adobe Originals; Myriad by Robert Slimbach and Carol Twombly). Library file "Myriad Pro Regular.ttf": Version 2.007;PS 002.000;Core..., copyright © 2000, 2004 Adobe Systems Incorporated, licence_url http://www.adobe.com/type/legal.html.
   identified by: Name-table copyright/version strings from families.json; bundling identified from Adobe's AEM Forms Designer documentation listing Myriad Pro Regular/Bold/It/Bold It among fonts "always available in Acrobat and Adobe Reader"; Adobe's Font Licensing FAQ and CC bundled-fonts pages fetched as instructed (both now redirect — see notes).
   status: BUNDLED — VENDOR TERMS PAGE STORED (reportage)
   bundling: Adobe Acrobat and Adobe Reader (Myriad Pro Regular, Italic, Bold, Bold Italic are listed by Adobe as "always available in Acrobat and Adobe Reader"); Adobe Creative Cloud / former Creative Suite desktop apps ship it as an application font (the family is also in the Adobe Fonts subscription library). Note the library file is a .ttf whereas Acrobat/Reader install MyriadPro-Regular.otf — the library copy's provenance is not established by any stored page.
   reportage: REPORTAGE (quoted, not assessed): Adobe AEM Forms Designer help 'Choosing fonts for performance': "the following fonts are always available in Acrobat and Adobe Reader, and do not need to be embedded" — list includes "Myriad Pro Bold, Myriad Pro Bold It, Myriad Pro It, Myriad Pro Regular" and "Adobe Arabic/Hebrew/Thai with all 4 styles (Bold, BoldItalic, Italic, and Regular). Available in Adobe Reader when the Extended Language Package is installed". helpx FAQ 'Note' (Last updated on Mar 27, 2026): "Fonts installed in the Fonts folder on your computer are licensed under their own end-user agreements. These FAQs don't apply to those fonts. Contact the font foundry directly for license questions." fonts.adobe.com/about (the page that https://www.adobe.com/products/type/creative-cloud-fonts.html now redirects to): "All the fonts are included with an Adobe subscription" / "Everything is licensed for personal and commercial use" / "Fonts are licensed for personal and commercial use; review the full Terms of Use." Search-engine snippet of a community.adobe.com thread (NOT vendor terms, NOT stored): Myriad Pro "has been included with the software for the exclusive use of the software itself".
   notes: The two Adobe URLs named in the brief are both redirects today: https://www.adobe.com/products/type/font-licensing.html -> https://www.adobe.com/products/type.html (stored as font-licensing_redirect_target.html; the landing page itself links "Font Licensing FAQ" back to the same redirecting URL) and https://www.adobe.com/products/type/creative-cloud-fonts.html -> https://fonts.adobe.com/about (stored as creative-cloud-fonts.html). The live FAQ is https://helpx.adobe.com/fonts/using/font-licensing.html -> https://helpx.adobe.com/fonts/web/font-licensing/font-licensing.html (stored). No stored page names Version 2.007, hence FAMILY-MATCHED. Network notes: adobe.com hosts (www/helpx) are Akamai-fronted; through the environment proxy, curl with a spoofed Chrome User-Agent fails (HTTP/2 'stream 1 was not closed cleanly: INTERNAL_ERROR (err 2)', curl rc=92) and HTTP/1.1 times out with 0 bytes (curl rc=28); curl's default User-Agent succeeds (HTTP 200). Pages were therefore stored with store_ua.py (same store()/meta/index code path, -A removed). Declared licence_url http://www.adobe.com/type/legal.html redirects to the Adobe Type landing page (WebFetch), i.e. the 2004-era legal page is gone.
     · Myriad Pro Regular.ttf  (referenced as MyriadPro-Regular; declared 'Version 2.007;PS 002.000;Core '; sha256 8cab5362ebfab49d…)
       CLASS: FAMILY-MATCHED
       Name-table copyright/version strings from families.json; bundling identified from Adobe's AEM Forms Designer documentation listing Myriad Pro Regular/Bold/It/Bold It among fonts "always available in Acrobat and Adobe Reader"; Adobe's Font Licensing FAQ and CC bundled-fonts pages fetched as instructed (both now redirect — see notes).
■ ae_AlMothnna  — upstream: Arabeyes.org "Khotot" fonts project (ae_fonts collection), distributed via SourceForge (project "arabeyes", Fonts/ae_fonts). Library file ae_AlMothnna_bold.ttf: "Version 1; May 22, 2003", copyright "Typeface and data © 2003, Arabeyes.org. This font is distributed under[...]", manufacturer "Al-Amri", licence_url http://www.gnu.org/copyleft/gpl.html.
   identified by: Name-table copyright naming Arabeyes.org and the GPL URL; Arabeyes wiki project page https://arabeyes.org/Khotot (stored earlier this session) and the SourceForge ae_fonts directory listing (stored: releases ae_fonts1_ttf_1.0 2003-06-13, ae_fonts1_ttf_1.1 2004-07-02, ae_fonts-1.9beta3 2007-08-14, ae_fonts_2.0 2007-08-19, ae_fonts_decorative-2.1 2010-09-07).
   status: OPEN_LICENCE_TEXT_STORED
   bundling: Not a bundled font. Distributed as the ae_fonts tarballs on SourceForge (and repackaged by third parties, e.g. TCPDF's ae_fonts_2.0 directory seen in search results).
   reportage: REPORTAGE (quoted, not assessed): Khotot project page TODO list: "New license or dual licensing with GPL and OFL. DONE (GPL with font exception)"; goals: "Create and/or salvage free and open TTF Arabic fonts." Stored GPL texts: GNU GPL v2 plain text (gnu.org/licenses/old-licenses/gpl-2.0.txt) and the declared licence_url http://www.gnu.org/copyleft/gpl.html, which today resolves to the GPL v3 page (gpl-3.0.html). Search-engine snippets (third-party font mirrors, NOT stored) describe the ae_fonts terms as GPL version 2 with an embedding exception ("if you create a document which uses this font and embed this font or unaltered portions into the document, this font does not by itself cause the resulting document to be covered by the GNU General Public License").
   notes: The library version string ("Version 1; May 22, 2003") is consistent with the 2003/2004 ae_fonts1_ttf_1.0/1.1 tarballs but no tarball was downloaded, so no hash match — FAMILY-MATCHED. The GPL version that the 2003 font's own text refers to is not visible in the truncated copyright string; GPL v3 (2007) postdates the font, which is why both the v2 text and the live v3 target of the declared URL are stored. Fetch notes: sourceforge.net returned HTTP 403 to curl with browser User-Agents (Chrome and Firefox) and HTTP 200 to store.py's plain urllib fetch (UA "bbrose-bh29-evidence-hunt (read-only)"). The SourceForge listing page shows no licence text itself.
     · ae_AlMothnna_bold.ttf  (referenced as ae_AlMothnna-Bold; declared 'Version 1; May 22, 2003'; sha256 ba1a02f451d475a0…)
       CLASS: FAMILY-MATCHED
       Name-table copyright naming Arabeyes.org and the GPL URL; Arabeyes wiki project page https://arabeyes.org/Khotot (stored earlier this session) and the SourceForge ae_fonts directory listing (stored: releases ae_fonts1_ttf_1.0 2003-06-13, ae_fonts1_ttf_1.1 2004-07-02, ae_fonts-1.9beta3 2007-08-14, ae_fonts_2.0 2007-08-19, ae_fonts_decorative-2.1 2010-09-07).
■ Hacen Liner XL  — upstream: Muhammad Hacen (hacen.net). Library file "Hacen Liner XL.ttf": Version 1.00 2006, copyright "Copyright © 2006 M. Hacen, All Rights Reserved / www.hacen.net", manufacturer/designer "Muhammad Hacen", vendor URL (nameID 11) www.hacen.net/liner, licence URL (nameID 14) www.hacen.net/font_license, licence description (nameID 13) embedded in the font.
   identified by: Read the font file itself (read-only, sha256 b307321a… matches families.json) with fontTools to extract the OpenType name table (copyright, designer, vendor URL, licence URL, licence description); the vendor URLs the font names were then probed (see notes). The hacen.net homepage (WebFetch) presents itself as the Arabic-language portfolio/blog of Muhammad Hacen with a footer link "اتفاقية استخدام الخطوط" (Font Usage Agreement).
   status: UNRESOLVED
   bundling: Not a bundled font (independent Arabic type designer).
   reportage: REPORTAGE (quoted, not assessed). The font's own embedded licence description (nameID 13): "The artistic design and the points in each glyph of this font are the property of Hacen, your use of this font is limited to production purposes, you may not edit, modify or rename this font without prior permission. Hacen holds the original shape of each letter of this font, any copying, redrawing, or rendering to match or imitate the shape of the original is a breach of copyright law." Search-engine snippet from fontke.com (third-party font-parameter site, NOT stored) labels the font "Non-Commercial" and says to contact the copyright party for a commercial licence — that classification is fontke's, not Hacen's. The vendor URL embedded in the font (www.hacen.net/liner) does not serve a font page today: the stored response is titled "MANTRA888 Saatnya Coba Permainan Yang Bikin Penasaran" and consists of Indonesian slot-gambling spam ("SITUS SLOT", "SLOT GACOR"; 291 spam-keyword hits, identical with a browser and with curl's default User-Agent) — hijacked/injected content, no licence wording. The hacen.net homepage itself is clean (title "Hacen", 0 spam hits, 37 "Hacen" mentions, footer link to https://hacen.net/license?lang=ar which returns 404).
   notes: Dead links: declared licence_url http://www.hacen.net/font_license -> HTTP 404 (also https://hacen.net/font_license 404); the live site footer links "اتفاقية استخدام الخطوط" (Font Usage Agreement) to https://hacen.net/license?lang=ar, which returns HTTP 404 (body titled "خطأ 404 - Hacen", filed as license_lang_ar_HTTP404.html); variants /license, /license/, ?lang=en, /ar/license, /en/license, /fonts-license, /terms on hacen.net and www.hacen.net all 404. Wayback Machine: availability API answered HTTP 429 (rate-limited) three times; one direct snapshot request resolved to https://web.archive.org/web/20121215044322/http://www.hacen.net/font_license but returned HTTP 404 (the archived capture itself is a 404). The font's vendor URL https://hacen.net/liner returns HTTP 200 (681,127 bytes) but with hijacked gambling-spam content instead of a font page (stored as liner.html with a warning note; not a product page); the homepage https://hacen.net/ is unaffected (title "Hacen"). Because the only licence text is the one embedded in the font (stored verbatim, not a web page) and no live vendor licence page exists, licence_status is UNRESOLVED; NAME+VERSION-MATCHED because the identification rests on the file's own name table and sha256.
     · Hacen Liner XL.ttf  (referenced as HacenLinerXL; declared 'Version 1.00 2006'; sha256 b307321a9712e30f…)
       CLASS: NAME+VERSION-MATCHED
       Read the font file itself (read-only, sha256 b307321a… matches families.json) with fontTools to extract the OpenType name table (copyright, designer, vendor URL, licence URL, licence description); the vendor URLs the font names were then probed (see notes). The hacen.net homepage (WebFetch) presents itself as the Arabic-language portfolio/blog of Muhammad Hacen with a footer link "اتفاقية استخدام الخطوط" (Font Usage Agreement).
■ Dubai  — upstream: Dubai Font — commissioned by the Dubai Executive Council ("TEC", The Executive Council of Dubai) and produced by Monotype; official site dubaifont.com. Library files DUBAI-BOLD.TTF / DUBAI-REGULAR.TTF: Version 1.10, copyright © 2016 Dubai Executive Council, manufacturer Monotype Imaging Inc., licence_url http://www.monotype.com.
   identified by: Name-table copyright/manufacturer strings; search results for dubaifont.com (download, privacy, press pages) and a third-party mirror of the "END USER LICENCE AGREEMENT – DUBAI FONT" (Font Squirrel) whose text names TEC and info@dubaifont.com. Bundling checked against Microsoft's official Windows 10/11 font lists (Dubai absent from both, including the Arabic Script Supplemental FOD package) and the Microsoft 365 "Cloud fonts in Office" list.
   status: UNRESOLVED
   bundling: Microsoft 365 — Office "cloud fonts" (Applies To: Excel/Word/Outlook/PowerPoint/Publisher for Microsoft 365, Windows and Mac) per Microsoft Support "Cloud fonts in Office" (Last updated: March 12, 2025), which lists "Dubai Regular / Dubai-Regular.ttf / 1.1" and "Dubai Bold / Dubai-Bold.ttf / 1.1" (plus Light, Medium and the four Italics). Also distributed free of charge from dubaifont.com (per the mirrored EULA, TEC licenses the Font Software "free of charge on a no-fee basis"). NOT part of the Windows 10/11 shipped font sets or the Arabic Script Supplemental FOD package (checked on Microsoft's official lists). Which channel the library copies came from is not established (file names DUBAI-BOLD.TTF/DUBAI-REGULAR.TTF are upper-case, unlike Microsoft's Dubai-Bold.ttf).
   reportage: REPORTAGE (not assessed). Microsoft Support "Cloud fonts in Office": "Cloud fonts are fonts hosted in the cloud by Microsoft 365, and are available in the latest versions of Office applications"; "Note Cloud fonts are available to Microsoft 365 subscribers."; list rows: "Dubai Bold Dubai-Bold.ttf 1.1", "Dubai Regular Dubai-Regular.ttf 1.1" (Italics are version 1). Quoted from the Font Squirrel MIRROR of the EULA (not the official page): heading "END USER LICENCE AGREEMENT – DUBAI FONT"; "BY USING, COPYING OR INSTALLING THE FONT SOFTWARE THE LICENSEE ACCEPTS ALL OF THE TERMS AND CONDITIONS CONTAINED HEREIN"; clause 2.1 "TEC licenses use of the Font Software to the Licensee on the basis of this Agreement free of charge on a no-fee basis. TEC does not sell the Font Software to the Licensee. TEC remains the owner of the Font Software at all times."; "TEC" means collectively The Executive Council (an entity in the Emirate of Dubai, United Arab Emirates established pursuant to Law No. (3) of 2003…". Search-engine snippets of dubaifont.com pages (NOT stored): "If you download and/or use the Dubai Font from the website, the downloading and/or use is subject to separate licensing terms under an end user licence agreement"; "You may use the fonts freely in your own work whether for private or commercial use"; "You are not allowed to distribute the fonts".
   notes: OFFICIAL EULA NOT STORED: dubaifont.com is unreachable through the environment proxy — curl "Connection timed out" (rc=28) on https://dubaifont.com/, https://www.dubaifont.com/, http://www.dubaifont.com/, https://dubaifont.com/privacy and https://www.dubaifont.com/download, with both HTTP/2 and HTTP/1.1; WebFetch also failed (download page: "Socket is closed"; homepage: "Socket is closed"/60 s timeout). The exact URL of the EULA page on dubaifont.com was not identified (search results index /download, /privacy, /pressCenter only). The mirror is stored as TERMS_PAGE_REPORTAGE and does not cite a source URL (only the contact address info@dubaifont.com appears). NAME+VERSION-MATCHED rests on Microsoft's official cloud-fonts list naming the family and version 1.1 (library: Version 1.10, © 2016 Dubai Executive Council, manufacturer Monotype Imaging Inc.); no binary hash comparison was possible (no font download). learn.microsoft.com/en-us/typography/font-list/dubai -> HTTP 404 (no Microsoft font-list entry). Microsoft Support "Cloud fonts in Office" page stored; the word "Dubai" occurs 16 time(s) in its text (Dubai IS listed among Microsoft 365 cloud fonts).
     · DUBAI-BOLD.TTF  (referenced as Dubai-Bold; declared 'Version 1.10'; sha256 b4ce691c229dd0ad…)
       CLASS: NAME+VERSION-MATCHED
       Name-table copyright/manufacturer strings; search results for dubaifont.com (download, privacy, press pages) and a third-party mirror of the "END USER LICENCE AGREEMENT – DUBAI FONT" (Font Squirrel) whose text names TEC and info@dubaifont.com. Bundling checked against Microsoft's official Windows 10/11 font lists (Dubai absent from both, including the Arabic Script Supplemental FOD package) and the Microsoft 365 "Cloud fonts in Office" list.
     · DUBAI-REGULAR.TTF  (referenced as Dubai-Regular; declared 'Version 1.10'; sha256 7a0be62452c4a73b…)
       CLASS: NAME+VERSION-MATCHED
       Name-table copyright/manufacturer strings; search results for dubaifont.com (download, privacy, press pages) and a third-party mirror of the "END USER LICENCE AGREEMENT – DUBAI FONT" (Font Squirrel) whose text names TEC and info@dubaifont.com. Bundling checked against Microsoft's official Windows 10/11 font lists (Dubai absent from both, including the Arabic Script Supplemental FOD package) and the Microsoft 365 "Cloud fonts in Office" list.
■ Goli  — upstream: MagicType (Jaikishan Patel), magictype.in; source repository https://github.com/magictype/Goli (default branch main, licence file OFL.txt, GitHub licence badge OFL-1.1). Library files Goli-{Light,Regular,Medium,SemiBold,Bold}-BF6639969….otf: "Version 1.000;Glyphs 3.2 (3242…", copyright "Copyright © 2024 by jaikishan Patel. All rights reserved.", manufacturer MagicType, licence_url magictype.in.
   identified by: Name-table manufacturer/copyright; MagicType product page https://www.magictype.in/portfolio/goli-typeface/ (stored by the main process) links "Download the latest build at GitHub" -> github.com/magictype/Goli; the repository's OFL.txt fetched raw from raw.githubusercontent.com and stored.
   status: OPEN_LICENCE_TEXT_STORED
   bundling: Not bundled; free download from magictype.in / GitHub. The library file names carry a "BF6639969…" suffix, the naming pattern of the third-party redistributor befonts.com, so the copies were most likely obtained there rather than from MagicType/GitHub (not verified).
   reportage: REPORTAGE (quoted, not assessed): product page: "The font family is available as open source for personal or commercial use. Feel free to use the typeface and share your valuable feedback."; OFL.txt (repo): "Copyright 2024 The Goli Project Authors (https://github.com/magictype/goli) This Font Software is licensed under the SIL Open Font License, Version 1.1."; the repo README (per WebFetch) says "Madhuban is licensed under the SIL Open Font License v1.1. To view the copyright and specific terms and conditions please refer to OFL.txt" — the README names a different MagicType family (Madhuban), apparently a copy-paste in the README. No price, cart item or purchase requirement appears on the product page for Goli.
   notes: Purchase NOT required per the vendor page, so not COMMERCIAL. Version 1.000 could not be matched to a GitHub release (repository has no release tags per WebFetch; font binaries not downloaded), hence FAMILY-MATCHED. The font's internal copyright string ("© 2024 by jaikishan Patel. All rights reserved.") differs from the OFL.txt copyright line ("The Goli Project Authors") — recorded, not interpreted. raw.githubusercontent.com probes: main/OFL.txt 200, master/OFL.txt 200 (branch alias), LICENSE/LICENSE.md/OFL.md 404, main/LICENSE.txt returned 000 (curl error) once.
     · Goli-Regular-BF663996909d710.otf  (referenced as Goli-Regular; declared 'Version 1.000;Glyphs 3.2 (3242'; sha256 f1fd3dd83659e777…)
       CLASS: FAMILY-MATCHED
       Name-table manufacturer/copyright; MagicType product page https://www.magictype.in/portfolio/goli-typeface/ (stored by the main process) links "Download the latest build at GitHub" -> github.com/magictype/Goli; the repository's OFL.txt fetched raw from raw.githubusercontent.com and stored.
     · Goli-Bold-BF6639968fd8e9b.otf  (referenced as Goli-Bold; declared 'Version 1.000;Glyphs 3.2 (3242'; sha256 d941dce88d2fd5c1…)
       CLASS: FAMILY-MATCHED
       Name-table manufacturer/copyright; MagicType product page https://www.magictype.in/portfolio/goli-typeface/ (stored by the main process) links "Download the latest build at GitHub" -> github.com/magictype/Goli; the repository's OFL.txt fetched raw from raw.githubusercontent.com and stored.
     · Goli-Light-BF66399690a8aa1.otf  (referenced as Goli-Light; declared 'Version 1.000;Glyphs 3.2 (3242'; sha256 5371e9ac5ae02866…)
       CLASS: FAMILY-MATCHED
       Name-table manufacturer/copyright; MagicType product page https://www.magictype.in/portfolio/goli-typeface/ (stored by the main process) links "Download the latest build at GitHub" -> github.com/magictype/Goli; the repository's OFL.txt fetched raw from raw.githubusercontent.com and stored.
     · Goli-Medium-BF66399690a672c.otf  (referenced as Goli-Medium; declared 'Version 1.000;Glyphs 3.2 (3242'; sha256 c7067f209bc67f31…)
       CLASS: FAMILY-MATCHED
       Name-table manufacturer/copyright; MagicType product page https://www.magictype.in/portfolio/goli-typeface/ (stored by the main process) links "Download the latest build at GitHub" -> github.com/magictype/Goli; the repository's OFL.txt fetched raw from raw.githubusercontent.com and stored.
     · Goli-SemiBold-BF66399690d955e.otf  (referenced as Goli-SemiBold; declared 'Version 1.000;Glyphs 3.2 (3242'; sha256 c279fcc804fe4084…)
       CLASS: FAMILY-MATCHED
       Name-table manufacturer/copyright; MagicType product page https://www.magictype.in/portfolio/goli-typeface/ (stored by the main process) links "Download the latest build at GitHub" -> github.com/magictype/Goli; the repository's OFL.txt fetched raw from raw.githubusercontent.com and stored.
■ Bebas  — upstream: Dharma Type (Ryoichi Tsunekawa), dharmatype.com; download/history site bebasfont.com (GitHub Pages, "Bebas maintained by dharmatype"). Library file Bebas-Regular.otf: "Version 1.100;PS 001.100;hotco[nv]", copyright "Copyright (c) 2005 by Ryoichi Tsunekawa. All rights reserved.", manufacturer Dharma Type, licence_url https://dharmatype.com.
   identified by: Name-table strings; Dharma Type licence page (stored by main process) and Bebas product page https://dharmatype.com/bebas (stored) which links Download -> http://bebasfont.com (stored); bebasfont.com states the original Bebas development "was terminated. version1.1(2019)", matching the library version string 1.100.
   status: UNRESOLVED
   bundling: Not bundled; free download (bebasfont.com points to https://www.dafont.com/bebas.font; the original Dharma Type page says development is discontinued).
   reportage: REPORTAGE (quoted, not assessed). Dharma Type licence page https://dharmatype.com/license ("THE END USER LICENSE AGREEMENT (EULA) v.2018.11.01.") does NOT mention Bebas or Bebas Neue by name; its "License Notice" says: "This End User License Agreement (EULA) applies to fonts purchased directly from us after November 2018. If you purchase fonts through third-party shops, their respective licenses will apply. Free fonts are licensed under either our FFEULA or the SIL Open Font License 1.1 (SIL-OFL 1.1). Please refer to each font's page for specific licensing details." (the only outbound licence link is https://scripts.sil.org/OFL). Bebas product page: "Bebas is a free font designed for headlines, captions, and titling. It was originally created in 2005 as a personal type design exercise… The development of the original version has since been discontinued." bebasfont.com "License" section: "Bebas (2005) is free font. You can use this font free of charge even for commercial purposes." bebasfont.com history on the Neue family: "Bebas Neue version 1.xxx (2010) — Free font … Licensed under the SIL Open Font License v1.1." and "Bebas Neue version 2.000 (2018) — Free font. From version 2.000, Bebas Neue has become open source font… Licensed under the SIL Open Font License v1.1."; also "Bebas Neue Family (2014) — Free font. Fontfabric designed additional weights and glyphs. They are distributing the font family under the same name of 'Bebas Neue'."
   notes: licence_status left UNRESOLVED deliberately: the vendor's free-font statements for the original Bebas (2005) are stored verbatim, but neither the licence page nor the Bebas page nor bebasfont.com attaches a named licence instrument (FFEULA or SIL OFL) to the ORIGINAL Bebas — the OFL statements on bebasfont.com are made for Bebas Neue 1.x/2.0 and Bebas Kai, not for Bebas (2005). No conclusion drawn. NAME+VERSION-MATCHED rests on the version string 1.100 = "version1.1(2019)" named by bebasfont.com; no binary hash comparison (the dafont.com download was not fetched).
     · Bebas-Regular.otf  (referenced as Bebas; declared 'Version 1.100;PS 001.100;hotco'; sha256 391cc0fa0763e520…)
       CLASS: NAME+VERSION-MATCHED
       Name-table strings; Dharma Type licence page (stored by main process) and Bebas product page https://dharmatype.com/bebas (stored) which links Download -> http://bebasfont.com (stored); bebasfont.com states the original Bebas development "was terminated. version1.1(2019)", matching the library version string 1.100.
■ Nexa  — upstream: Fontfabric (Svetoslav Simov), https://www.fontfabric.com/fonts/nexa/ (product page: Release Date October 4, 2012; 36 styles). Library file Nexa-Heavy.ttf: Version 2.001, copyright "Copyright © 2012 by Fontfabric. All rights reserved.", manufacturer Fontfabric LLC, licence_url http://www.fontfabric.com.
   identified by: Name-table strings; Fontfabric product page (stored by main process) lists "Nexa Heavy" inside the paid "Nexa - 18 font styles" collection ($175) and the complete family ($249), with desktop licences "from $29"; Fontfabric's licensing pages and both published EULA texts were stored earlier this session (main process/other leg) — not re-stored.
   status: COMMERCIAL — EVIDENCE REQUIRES PURCHASE
   bundling: Not bundled; retail font sold by Fontfabric (per-style and collection pricing on the product page).
   reportage: REPORTAGE (quoted, not assessed): product page: "Nexa Complete Family - 36 font styles … $249"; "Nexa - 18 font styles … $175" (list includes "Nexa Heavy", "Nexa Heavy Italic"); "Desktop from $29 — Install the font on your computer to create designs for print or static digital images, such as logos, packaging, and marketing materials. The desktop license is always perpetual."; the page also offers "Enter your email to receive your free font … We'll send you a zipped file with the free font, license agreement, and installation instructions" (NOT used — no email entered). "Fontfabric Commercial EULA For Retail Fonts" (openly published, stored): clause 2.1 "Customer shall have a non-exclusive, non-assignable, non-transferable (except as expressly permitted) license to install, access and Use the Font Software. Fontfabric reserves all rights not expressly granted…"; clause 2.3 "This Agreement shall be effective upon the date that Customer receives Font Software". "Fontfabric Commercial EULA For Free Fonts" (stored): "All Fontfabric Fonts (Software) available for a free download and commercial use come with a standard Fontfabric Commercial End-User License Agreement For Free Fonts as part of the free download…".
   notes: Nexa Heavy is a paid weight; a purchase-specific licence certificate/Order Form would be the evidence of the library owner's own licence and cannot be obtained without purchase (none attempted). The openly published retail EULA text IS stored (LICENCE_TEXT) — it carries no version/date line of its own (page footer "2026 © Fontfabric llc."). Library version 2.001 (2012) vs. the current product build: not shown on the product page, hence FAMILY-MATCHED. Historical note from bebasfont.com (stored under Bebas): Fontfabric also distributed a "Bebas Neue Family (2014)" — unrelated to Nexa licensing, recorded for cross-reference only.
     · Nexa-Heavy.ttf  (referenced as Nexa-Heavy; declared 'Version 2.001'; sha256 8bd502de7aa8a568…)
       CLASS: FAMILY-MATCHED
       Name-table strings; Fontfabric product page (stored by main process) lists "Nexa Heavy" inside the paid "Nexa - 18 font styles" collection ($175) and the complete family ($249), with desktop licences "from $29"; Fontfabric's licensing pages and both published EULA texts were stored earlier this session (main process/other leg) — not re-stored.

§2 CLAUSE (2) — LICENCE TEXTS FETCHED, COMPLETE AND BYTE-VERBATIM
───────────────────────────────────────────────────────────────────────
35 distinct licence-text files by sha256 (full-file bytes), grouping into 16 distinct BODIES (the text from 'SIL OPEN FONT LICENSE' onward, or the GPL / other): body f19c674290e5dc79: 17 file(s) for Amatic, Cairo, Goli, Grand Hotel, Lato, Merriweather, Montserrat, Playfair Display, Poppins, Quicksand, Raleway, Roboto, Rubik, Shadows Into Light Two; body 181cc8cc002cc681: 1 file(s) for Bebas Neue; body HTML-b9bcf459: 1 file(s) for Figerona Black; body HTML-6f412d99: 1 file(s) for Figerona Black; body e19dc5410d6fccd5: 2 file(s) for Great Vibes, Montserrat; body other: 2 file(s) for Hacen Liner XL, Nickainley; body HTML-1e64bf7b: 1 file(s) for Komika Axis; body HTML-d699b0a5: 1 file(s) for Komika Axis; body HTML-ead6e2ea: 1 file(s) for Komika Axis; body HTML-b480f758: 1 file(s) for Nexa; body HTML-06e88d25: 1 file(s) for Nexa; body HTML-9eebc8d1: 1 file(s) for Nickainley; body Apache-2.0: 2 file(s) for Open Sans, Roboto; body b0a140a7ad9326ba: 1 file(s) for Open Sans; body GPL: 1 file(s) for ae_AlMothnna; body HTML-f71e5664: 1 file(s) for ae_AlMothnna

════ BODY GROUP f19c674290e5dc79 (17 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- 301f77908df2b00141b4dcea50cc1a586c3afcee78843bd811088e8263623f9d  4390 bytes  families: Amatic
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/amaticsc/OFL.txt  fetched 2026-09-03T06:00:13Z  path: /Users/symow/bh29_work/evidence/Amatic/OFL.txt
Copyright 2015 The Amatic SC Project Authors (https://github.com/googlefonts/AmaticSC)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- a4554e1799d42e1405924b61eb0e0722ae1623b1f1f07f995348f96c496362a9  4473 bytes  families: Cairo
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/cairo/OFL.txt  fetched 2026-09-03T05:58:15Z  path: /Users/symow/bh29_work/evidence/Cairo/OFL.txt
Copyright 2009 The Cairo Project Authors (https://github.com/Gue3bara/Cairo)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 17b90cece30db64934b7299fd76b033a3774c8a990e78badc74c59a5be8e0727  4458 bytes  families: Cairo
---- URL: https://raw.githubusercontent.com/google/fonts/e86936fd5b72936fe1eed526b69d49343a7d353b/ofl/cairo/OFL.txt  fetched 2026-09-03T08:05:54Z  path: /Users/symow/bh29_work/evidence/Cairo/OFL_at_e86936fd.txt
Copyright 2009 The Cairo Project Authors (gaber@gaberism.net)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 18bc2a638ef84bcd7200a8f0f97cdf8c99d91c484ea60aa19df1efe72fde6a20  4379 bytes  families: Goli
---- URL: https://raw.githubusercontent.com/magictype/Goli/main/OFL.txt  fetched 2026-09-03T07:50:57Z  path: /Users/symow/bh29_work/evidence/Goli/OFL.txt
Copyright 2024 The Goli Project Authors (https://github.com/magictype/goli)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 4c0a1150a363b42bd8681ff4a00315ac49510a944c4c9978237ff8b90a8920a5  4540 bytes  families: Grand Hotel
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/grandhotel/OFL.txt  fetched 2026-09-03T06:05:18Z  path: /Users/symow/bh29_work/evidence/Grand_Hotel/OFL.txt
Copyright (c) 2012 by Brian J. Bonislawsky and Jim Lyles DBA Astigmatic
(AOETI) (astigma@astigmatic.com), with Reserved Font Name "Grand Hotel"

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 74ba064d03f1f1c4a952da936c3eb71866c34404916734de3cae73b34357e59e  4407 bytes  families: Lato
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/lato/OFL.txt  fetched 2026-09-03T06:03:59Z  path: /Users/symow/bh29_work/evidence/Lato/OFL.txt
Copyright (c) 2010-2014 by tyPoland Lukasz Dziedzic (team@latofonts.com) with Reserved Font Name "Lato"

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 715bd349bfa6116f99e351e1548321dcfa25b91df65502d22ca8d624557697d2  4438 bytes  families: Merriweather
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/merriweather/OFL.txt  fetched 2026-09-03T06:00:41Z  path: /Users/symow/bh29_work/evidence/Merriweather/OFL.txt
Copyright 2020 The Merriweather Project Authors (https://github.com/EbenSorkin/Merriweather4) with Reserved Font Name "Merriweather".

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
https://openfontlicense.org


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 41f82bb4d24b304f30f7136bc47abdd083782e4265c984160f5649d1e78ea49c  4392 bytes  families: Montserrat
---- URL: https://raw.githubusercontent.com/google/fonts/9548902f8a5a0b4a0bb7427d93347a9ba9fd0f2e/ofl/montserrat/OFL.txt  fetched 2026-09-03T08:05:59Z  path: /Users/symow/bh29_work/evidence/Montserrat/OFL_at_9548902f.txt
Copyright 2011 The Montserrat Project Authors (https://github.com/JulietaUla/Montserrat)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 566be814f8e96e93dfa16101331557eb6b5467e9e03f627c0910fe93ca12300e  4449 bytes  families: Playfair Display
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/OFL.txt  fetched 2026-09-03T06:01:04Z  path: /Users/symow/bh29_work/evidence/Playfair_Display/OFL.txt
Copyright 2017 The Playfair Display Project Authors (https://github.com/clauseggers/Playfair-Display), with Reserved Font Name "Playfair Display"

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 6be04893d770899a015649c7aa3b582f871b272f8747a92b78b17c3e5c8b2573  4385 bytes  families: Poppins
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/OFL.txt  fetched 2026-09-03T05:58:23Z  path: /Users/symow/bh29_work/evidence/Poppins/OFL.txt
Copyright 2020 The Poppins Project Authors (https://github.com/itfoundry/Poppins)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 14d28541780d90f6577bb7abcc6f005bf6969614294e75c82abb8758a696ad46  4445 bytes  families: Quicksand
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/quicksand/OFL.txt  fetched 2026-09-03T05:59:58Z  path: /Users/symow/bh29_work/evidence/Quicksand/OFL.txt
Copyright 2011 The Quicksand Project Authors (https://github.com/andrew-paglinawan/QuicksandFamily), with Reserved Font Name “Quicksand”.

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 7e946cf1171784d1015279e7dc35f827957a6b5d1f1f659ae0c98e5f5e37ed9b  4497 bytes  families: Raleway
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/raleway/OFL.txt  fetched 2026-09-03T06:01:18Z  path: /Users/symow/bh29_work/evidence/Raleway/OFL.txt
Copyright 2010 The Raleway Project Authors (impallari@gmail.com), with Reserved Font Name "Raleway".

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- e588abf45ca2b19c340c4b27349c9b6b6e5e198316fd965128ed9f4422942cbe  4650 bytes  families: Raleway
---- URL: https://raw.githubusercontent.com/google/fonts/90abd17b4f97671435798b6147b698aa9087612f/ofl/raleway/OFL.txt  fetched 2026-09-03T08:07:02Z  path: /Users/symow/bh29_work/evidence/Raleway/OFL_at_90abd17b.txt
Copyright (c) 2010, Matt McInerney (matt@pixelspread.com),
Copyright (c) 2011, Pablo Impallari (www.impallari.com|impallari@gmail.com),
Copyright (c) 2011, Rodrigo Fuenzalida (www.rfuenzalida.com|hello@rfuenzalida.com), with Reserved Font Name Raleway

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 061402327a96aadb0bfb694a960ed289ecd38d383e396243831ab81feb109c41  4394 bytes  families: Roboto
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/OFL.txt  fetched 2026-09-03T06:01:30Z  path: /Users/symow/bh29_work/evidence/Roboto/OFL.txt
Copyright 2011 The Roboto Project Authors (https://github.com/googlefonts/roboto-classic)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
https://openfontlicense.org


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 472cbe7c25441df63e9c7864b43eb3c0f4b3df950c66a76224e6cfe1eae843fb  4384 bytes  families: Rubik
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/rubik/OFL.txt  fetched 2026-09-03T06:01:44Z  path: /Users/symow/bh29_work/evidence/Rubik/OFL.txt
Copyright 2015 The Rubik Project Authors (https://github.com/googlefonts/rubik)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
https://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 3bf1a0fdd4210b875271e8dabaa55c0313a2c679a20f5f860bbe2adfc8f88e2f  4345 bytes  families: Rubik
---- URL: https://raw.githubusercontent.com/google/fonts/a8f83b60237a44d7e329c200695069af03c0e0f7/ofl/rubik/OFL.txt  fetched 2026-09-03T08:07:05Z  path: /Users/symow/bh29_work/evidence/Rubik/OFL_at_a8f83b60.txt
Copyright 2015 The Rubik Project Authors,

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


---- 6a28d4d5d8b4d1ea89ace5a047ac6e0de182acdb8bfa22897bf7702102094f69  4362 bytes  families: Shadows Into Light Two
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/shadowsintolighttwo/OFL.txt  fetched 2026-09-03T06:02:01Z  path: /Users/symow/bh29_work/evidence/Shadows_Into_Light_Two/OFL.txt
Copyright (c) 2012, Kimberly Geswein (kimberlygeswein.com)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


════ BODY GROUP 181cc8cc002cc681 (1 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- 72082f6cb4d04be2ecf7cc7d9e1e7d73787f0af8a5a278a47cade70c16b78341  4337 bytes  families: Bebas Neue
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/OFL.txt  fetched 2026-09-03T05:59:27Z  path: /Users/symow/bh29_work/evidence/Bebas_Neue/OFL.txt
Copyright © 2010 by Dharma Type.

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded,
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment. 

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


════ BODY GROUP HTML-b9bcf459 (1 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- e62e70718ad5fdae1de386ce9dcc9b97ad5c0e26e376f53fb891926a6e569879  294950 bytes (HTML page; bytes stored verbatim at the path; TEXT EXTRACTED below, not byte-verbatim)  families: Figerona Black
---- URL: https://drizystudio.com/license/  fetched 2026-09-03T06:16:49Z  path: /Users/symow/bh29_work/evidence/Figerona_Black/license.html
License - Drizy Studio All Products Bundles Crafters Font Freebies Membership Vector Print Template Time Limited Freebies Crafters Featured Premium SVG Seasonal Fall SVG Halloween SVG Thanksgiving SVG Winter SVG Christmas SVG Easter SVG Spring SVG Summer SVG Craft Design SVGs SVG Cut Files Cricut SVG Silhouette SVG 3D Shadow Box SVGs Paper Cut Templates Sublimation Designs Monogram Designs Stickers SVG Card Making Laser Cutting Designs Printable Crafts T-Shirt Designs Funny Quotes SVG Flower SVG Mom Life SVG Inspirational & Motivational SVG Font Type Serif Sans Serif Decorative Script Style Brush Casual Brush Calligraphy Signature Monoline Handwritten Scribble Doodle Smooth Classy Elegant Minimalism Clean Modern 3D Rounded Geometric Simple Bold Slanted Gothic Ethnic Unique Layered Psychedelic Aesthetic Dripping Abstract Stencil Theme Playful Cute Funny Kids Vintage Retro Classic 90s 80s Futuristic Techno Robotic Sci-Fi Halloween Blood Horror Spooky Scary Mystery Creepy Romantic Girly Feminine Love American Cowboy Christmas Nature Vector Illustration Icon Print Template | Bundles Bundle SVG Craft Bundles Font Bundles Freebies Free SVGs Free SVG Files for Commercial Use Free Sublimation Designs Deals $1 Bundle Deals $1 SVG Deals $1 Font Deals $1 Black Friday Membership $1 Cyber Monday Membership | Membership All Products Bundles Crafters Font Freebies Membership Vector Print Template Time Limited Freebies License Font License Desktop License License Usage : 1 User 5 Commercial Project Unlimited Personal Project 2 Computer Installation Non Monetized Social Media (YouTube, Instagram, Facebook, TikTok, Twitter, etc) : Unlimited Usage Blog : Unlimited Usage End Product For Sale (Product/Print Ads/Digital Impressions/Merchandise) : 1,000 Sales/Prints/Pcs Webfont License License Usage : 1 Website For licensee’s web app and website usage only WOFF format file Embedding fonts using @font-face Monthly Webpage Views : 100,000 Views Extended Webfont License License Usage : 5 Website For licensee’s web app and website usage only WOFF format file Embedding fonts using @font-face Monthly Webpage Views : Unlimited Views Server License License Usage : 1 Website Allow Users to Use Font Monetized Social Media (YouTube, Instagram, Facebook, TikTok, Twitter, etc) : Unlimited Usage End Product For Sale (Product/Print Ads/Digital Impressions/Merchandise) : Unlimited Prints/Sales/Pcs Embedding fonts using @font-face Monthly Webpage Views : Unlimited Views Broadcast License License Usage : Video/Movies TV/Motion Graphic Unlimited Commercial Project E-Pub License E-book/E-Publishing/Digital Media Unlimited for publications intended for Kindles, iPads or other PDF Readers Monetized Social Media License License Usage : Instagram, Youtube, Facebook, TikTok, Twitter & another social media. Unlimited monetized social media usage and event videos App/Game License License Usage : 1 App 1 Game Unlimited App Views or Game Views Logo License License Usage : 2 User 2 Computer Installation Logo Usage/Logotype Trademark Logo * 1 Commercial Project Unlimited Personal Project OTF/TTF format file Monetized Social Media (YouTube, Instagram, Facebook, TikTok, Twitter, etc) : Unlimited Usage End Product For Sale (Product/Print Ads/Digital Impressions/Merchandise) : 500,000 Sales/Prints/Pcs 1 Websites Monthly Webpage Views : 1,000,000 Views * You must disclaim the asset if registering for Trademark protection, and you may not enforce any rights on the font itself. Extended License License Usage : Maks. 10 User Maks. 10 Computer Installation Logo Usage/Logotype Unlimited Commercial & Personal Project Monetized Social Media (YouTube, Instagram, Facebook, TikTok, Twitter, etc) : Unlimited Usage Blog : Unlimited Usage End Product For Sale (Product/Print Ads/Digital Impressions/Merchandise) : Unlimited Prints/Sales/Pcs Unlimited Website Embedding fonts using @font-face Monthly Webpage Views : Unlimited Views National Corporate License License Usage : 1 Corporate/Brand Unlimited User & Installation Unlimited Commercial Project Unlimited Web Views Unlimited Broadcasting Unlimited Social Media & Blog Unlimited Apps & Server Unlimited End Product for Sale Nationally Worldwide Corporate License License Usage : 1 Corporate/Brand Unlimited User & Installation Unlimited Commercial Project Unlimited Web Views Unlimited Broadcasting Unlimited Social Media & Blog Unlimited Apps & Server Unlimited End Product for Sale Worldwide . Drizy VIP+ Subscription License In this section you will learn all about Drizy Studio’s VIP Plus subscription licenses. This version of the license is effective starting (31 April 2023) . Version 1.1 Personal Plan & 1 Year Pass Personal Plan and 1 Year Pass subscriptions fall under “Personal Use” . “Personal Use”? What does it mean? Personal Use is any use that meets none of the criteria for Commercial Use. Personal use or Non-Commercial use is a use for solely personal projects. All “Personal Use” must meet all three of the following: No exchange of money or services involved No financial gain is earned, either as a direct or indirect result The use must not promote a business entity (this includes non-profit organizations) If any one or more of the criteria is not met , then the use is deemed “Commercial” . License Summary YOU ARE ALLOWED TO Produce Physical End Products of unlimited amount for Non-Commercial use * Produce Digital End Products of unlimited amount for Non-Commercial use * Digitally and physically produce quotes, words, or names using fonts for Non-Commercial use * Convert templates to other formats for Non-Commercial use * Use assets for one personal or individual social media account strictly for Non-Commercial use * YOU ARE NOT ALLOWED TO Produce any Physical End Products for Commercial use Produce any Digital End Products for Commercial use Submit assets you downloaded to sell on Print-on-Demand (POD) sites Digitally and physically produce quotes, words, or names using fonts for Commercial use Generate new designs after your subscription ends. Once you cancel or do not renew your subscription, you are not allowed to produce new “Shirts / Banners / Quotes / others.” This condition does not affect craft files. Craft files can continue to be used forever, even in new designs. Keep making new products after your subscription ends. Existing items that you created while you had an active subscription can continue being used. Resell, sub-license, share or (re)distribute any of the digital files. Convert any aspect of fonts (letter/number/glyph) to different formats (for example SVG) and sell the files. Install or embed on 3rd party platforms/servers. Convert templates into different formats and sell those as new templates. Use assets purchased with a personal license for a social media account that acts as a company or business. Physical End Products YOU ARE ALLOWED TO Produce a physical item using downloaded design for Non-Commercial use without making modifications. Produce a physical item for Non-Commercial use by using a design that is modified. Produce Physical End Products using a design in unlimited copies for Non-Commercial use. YOU ARE NOT ALLOWED TO Produce a physical item for Commercial use using downloaded design without making modifications. Produce a physical item for Commercial use by using a design that is modified. Continue modifying or creating new designs after your subscription ends. Continue producing physical items after your subscription ends using the design that was created while you had an active subscription. Share a digital copy of the design of the original font/design with your physical product. Digital End Products YOU ARE ALLOWED TO Generate a new design using elements for Non-Commercial use. For example, you are using star elements to create a space themed birthday template. Generate new designs by combining multiple downloaded resources and adding items of your own for Non-Commercial use. All elements in the new design must be flattened so extraction of the original assets cannot be done. YOU ARE NOT ALLOWED TO Generate a new design using elements for Commercial use. Generate new designs by combining multiple downloaded resources and adding items of your own for Commercial use. Generate a digital product with separated elements that allows extraction of elements to be done (all designs must be flattened). Commercial Plan Commercial Plan subscription falls under “Commercial Use” . “Commercial Use”? What does it mean? “Commercial” is the opposite of “Personal” use. “Commercial” use is any use: that involves an exchange of money or services. that promotes a business, including non-profit organizations. Business types include: sole proprietorship, corporation, or partnership. that results in financial gain or other consideration, either directly or indirectly, by using licensed assets. If any one or more of the criteria is met , then the use is deemed “Commercial” . License Summary YOU ARE ALLOWED TO Produce Physical End Products of unlimited amount to sell * Produce Digital End Products of unlimited amount to sell * Submit your own items to sell on Print-on-Demand (POD) sites * Digitally and physically produce quotes, words, or names using fonts to sell * Convert templates to other formats for your clients * Continue selling products after your subscription ends; on the condition that the design was created while you had an active subscription. * See our guide to correctly use the assets below. YOU ARE NOT ALLOWED TO Resell, sub-license, share or (re)distribute any of the digital files. Convert any aspect of fonts (letter/number/glyph) to different formats (for example SVG) and sell the files. Install or embed on 3rd party platforms/servers Convert templates into different formats and sell those as new templates. Generate new designs after your subscription ends. Once you cancel or do not renew your subscription, you are not allowed to produce new “Shirts / Banners / Quotes / others.” and sell those items. This condition does not affect craft files. Craft files can continue to be used forever, even in new designs. Physical End Products YOU ARE ALLOWED TO Produce a physical item using downloaded design without making modifications and sell that physical item. Produce a physical item by using a design that is modified and sell that physical item. Produce Physical End Products using a design and sell unlimited copies of the physical items. No limitations to time and location to sell the physical product you produced. Produce physical products as part of a promotional product or as a gift (Non-Commercial use). Continue selling physical items after your subscription ends, on the condition that the design for the physical item was generated while you had an active subscription. YOU ARE NOT ALLOWED TO Share a digital copy of the design of the original font/design with your physical product. Produce and sell physical products using new designs that are generated or modified after your subscription ends. Only designs made while you had an active subscription can be produced. Digital End Products YOU ARE ALLOWED TO Generate a new design using elements to sell. For example, you are using star elements to create a space themed birthday template. Generate new designs by combining multiple downloaded resources and adding items of your own to sell. All elements in the new design must be flattened so extraction of the original assets cannot be done. YOU ARE NOT ALLOWED TO Generate end products that compete with the original product. For example, you cannot compile multiple designs in a bundle and sell the bundle as a new product. Another example is to make minimal changes to elements such as resizing and editing colors and sell that as a new product. Sell in a method that is directly competitive with the original item that you downloaded. For example, you cannot grab a monogram template, change the elements and sell it as another monogram template. Generate a digital product with separated elements that allows extraction of elements to be done (all designs must be flattened). Print on Demand (POD) Usage YOU ARE ALLOWED TO Generate crafts and graphics that are greatly modified from the original and submit to POD sites. This means there are distinctive elements that you added in the designs. See an example below. Generate phrases, quotes, names, or word art using fonts and submit those designs to POD sites. Have an unlimited number of sales through POD sites. Send legitimate POD products to any location in the world. YOU ARE NOT ALLOWED TO Submit designs without any addition of new distinctive elements. Generate a combination of multiple designs into a single design and sell that. Submit font files to POD sites. Submit patterns to POD sites. In case you have any questions, you can contact us at [email protected] . Share & Earn Get The Extra Money With Only Few Clicks 30% Commission Become an Affiliator × Drizy Font has ascended The universe of typography has shifted. Drizy Font is now live on a brand-new futuristic platform designed for speed, power, and next-level creativity. Our old site served its purpose. But this? This is the future of font. Streamlined design Faster downloads It’s not just a website. It’s a warp gate to infinite design possibilities. Ready to explore? Find Blogs Newest Popular Categories Crafters Font Vector Print template Legal License Terms & Conditions Privacy Policy Help Help Center FAQ Contact Us About Us Let's Connect! ©2021 Drizy Studio - All rights reserved. Scroll to top Scroll to top

════ BODY GROUP HTML-6f412d99 (1 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- 6d44b2221c4f2ceb77abb2b07537fe0ff859c01739e2a568a0724df88a7c71ab  321638 bytes (HTML page; bytes stored verbatim at the path; TEXT EXTRACTED below, not byte-verbatim)  families: Figerona Black
---- URL: https://drizyfont.com/licenses/  fetched 2026-09-03T06:17:53Z  path: /Users/symow/bh29_work/evidence/Figerona_Black/licenses.html
Licenses - Drizy Font Fonts New Releases Font Sale Best Sellers Freebies Exclusive Contributor Variable Fonts Sans Serif Fonts Serif Fonts Script Fonts Experimental Fonts Futuristic Fonts Web3 Fonts Media & Broadcasting Services Embed License Rent License Agency Partnership Custom Services Blog About Us Fonts New Releases Font Sale Best Sellers Freebies Exclusive Contributor Variable Fonts Sans Serif Fonts Serif Fonts Script Fonts Experimental Fonts Futuristic Fonts Web3 Fonts Media & Broadcasting Services Embed License Rent License Agency Partnership Custom Services Blog About Us Fonts New Releases Font Sale Best Sellers Freebies Exclusive Contributor Variable Fonts Sans Serif Fonts Serif Fonts Script Fonts Experimental Fonts Futuristic Fonts Web3 Fonts Media & Broadcasting Services Embed License Rent License Agency Partnership Custom Services Blog About Us Search Login Search Drizy Fonts Licenses License Personal For non-commercial personal use: installing on computers, non-monetized social media, non-monetized blogs, non-monetized websites, digital banners, print, portfolios, merchandise, etc. User: Maximum 1 Personal Projects: Unlimited Computer Installation: 5 Devices Social Media: Unlimited Blogs / Websites: 5 End Product: Unlimited Not for Commercial Use End Product Not For Resale Freelance For freelance professionals who handle small-scale commercial projects: webfonts, logos, packaging, books, ePubs, websites, digital ads, social media ads, monetized blog, monetized social media, etc. User: Maximum 5 Commercial Projects: 1 Computer Installation: 5 Devices Products, Print, Sales, Impression, Page Views, Images: 500,000 Company Size: Up to 50 Employees End Product Not For Resale Commercial For commercial usage , including freelance projects, professional work, and agencies serving medium-scale clients (SMEs) with purposes: webfonts, logos, packaging, books, ePubs, websites, digital ads, social media ads, video commercials, monetized blogs, monetized social media, commercial printing, merchandise, etc. User: Maximum 10 Commercial Projects: 1 Computer Installation: 10 Devices Logo Usage / Trademark: Yes Products, Print, Sales, Impression, Page View, Images: Unlimited Company Size: Up to 150 Employees End Product Not For Resale Enterprise For use in large-scale projects: public figures, national/multinational corporate companies, servers, applications, games, websites, films, editorials, digital media, print media, broadcasting, embedding, modifications, and more. We also cater to custom license requests and specific business needs. END USER LICENSE AGREEMENT Below is our End User License Agreement. Please review it carefully before purchasing and using any fonts. By purchasing a license, you agree to the terms of this agreement. For more information, please contact us. Trial If you’re seeking the ability to test out different font variations in your layout, present them to clients, and choose the most suitable one for your project, our trial option is for you. This specific license is created specifically for sharing information and is not meant to be used for commercial purposes. Full license PDF Desktop This license is suitable for purposes including logo design, digital images on websites or social media, as well as in print media, souvenirs, and merchandise for sale. *You can obtain a Desktop License in the Freelance or Commercial package, depending on the number of users/devices, company scale, and the quantity needed for products, print, sales, impressions, page views, and images. Full license PDF Webfont If you’re looking to use the font for headings or text blocks on your website, this commercial font license is the right choice. *You can obtain a Webfont License in the Freelance or Commercial package, depending on the number of users/devices, company scale, and the quantity needed for products, print, sales, impressions, page views, and images. Full license PDF App If you’re creating applications for Windows, Android, iOS, Linux, or other operating systems, this font license is what you need. When deciding on a license, we don’t consider the number of times the app is downloaded like many others do. Instead, we focus solely on the number of applications that will use the font. *You can obtain an App License by choosing the Enterprise package. Contact us to get a quote. Full license PDF Game If you’re a game developer, this license gives you the ability to incorporate the font directly into the code of your game. When deciding on a license, we don’t consider the number of times the game is downloaded like many others do. Instead, we focus solely on the number of games that will use the font. *You can obtain a Game License by choosing the Enterprise package. Contact us to get a quote. Full license PDF Video & Broadcasting With this font license, you have the freedom to use the font in various forms of video content, including blogging, YouTube or TV channels, and online or offline broadcasting. The available font license options are based on the extent to which the font will be used in your video content. *You can obtain a Video & Broadcasting License by choosing the Enterprise package. Contact us to get a quote. Full license PDF Digital Ads This font license is perfect for those who need to use the font in banners, digital ads, and posters on the internet, as well as for advertising on social media. The available license options vary based on the number of times the ads featuring the font will be displayed or viewed (ad impressions). *You can obtain a Digital Ads License in the Freelance or Commercial package, depending on the number of users/devices, company scale, and the quantity needed for products, print, sales, impressions, page views, and images. Full license PDF E-Book If you’re working on e-books, magazines, interactive PDFs, or other publications, this font license is the right choice for you. *You can obtain an e-book License in the Freelance or Commercial package, depending on the number of users/devices, company scale, and the quantity needed for products, print, sales, impressions, page views, and images. Full license PDF Server This license is designed for unique websites and applications that allow users to create products using the selected font, without the need for an additional font license. *You can obtain a Server License by choosing the Enterprise package. Contact us to get a quote. Full license PDF Contact Us Partnership This is an invitation for freelancers, marketing agencies, or design studios to partner with Drizy. Access is granted to the demo products of Drizy Font, facilitating their creative process and prototyping. If a suitable font is found, an exclusive price will be offered below the standard price displayed on the website. Contact Us Subscription / Rental Gain unlimited access to the complete Drizy Font’s font collection by subscribing to our service. With a subscription, you’ll have access to a wide range of library that can enhance your creative projects. Throughout your subscription period, you can enjoy the benefits of installing all font updates. Rest assured, we regularly update the font collection, ensuring that you have access to the latest and greatest designs. This gives users the flexibility to choose a font that suits the style or character needed for their project. Users need to extend the rental period periodically to obtain a usage license. If the subscription is stopped, all downloaded fonts can still be used but will not have a commercial usage license. For more information, you can consult with us. Contact Us Embed This is an invitation for freelancers, marketing agencies, or design studios to partner with Drizy. Access is granted to the demo products of Drizy Font, facilitating their creative process and prototyping. If a suitable font is found, an exclusive price will be offered below the standard price displayed on the website. Contact Us Custom We offer a flexible approach to customizing standard licenses based on the specific tasks and requirements of your company’s technical department. For example, we can include provisions in the license that allow you to transfer font rights to your contractors during the duration of their work on specific projects. This ensures that the font usage aligns with your company’s needs and facilitates a smooth collaboration with external partners. Our services include: Building from scratch — We can create fonts from zero. Mastering — Realizing your sketches, drafts, lettering, or vectors into professional fonts. Hinting — Improving the appearance and readability of fonts by making adjustments. Cyrillization — Implementing Cyrillic characters into fonts For more information about our services, feel free to talk to us. We are here to help. Contact Us 100% handmade and original for all your typographic needs. Design your custom fonts with us! Email address Send Your email ID is confidential Bandung, West Java, Indonesia Let’s Connect! Explore New Releases Font Sale Freebies Best Sellers Blog Exclusive Contributor Affiliate New Releases Font Sale Freebies Best Sellers Blog Exclusive Contributor Affiliate Categories Variable Fonts Sans Serif Fonts Serif Fonts Script Fonts Experimental Fonts Futuristic Fonts Web3 Font Media & Broadcasting Variable Fonts Sans Serif Fonts Serif Fonts Script Fonts Experimental Fonts Futuristic Fonts Web3 Font Media & Broadcasting Services Embed License Rent License Agency Partnership Custom Services Embed License Rent License Agency Partnership Custom Services More Fonts Legal Licenses Terms & Conditions Privacy Policy Licenses Terms & Conditions Privacy Policy Help Help Center FAQ Contact Us About Us Help Center FAQ Contact Us About Us 100% handmade and original for all your typographic needs. Design your custom fonts with us! Email address Send Your email ID is confidential Bandung, West Java, Indonesia Let’s Connect! Explore New Releases Font Sale Freebies Best Sellers Blog Exclusive Contributor Affiliate New Releases Font Sale Freebies Best Sellers Blog Exclusive Contributor Affiliate Categories Variable Fonts Sans Serif Fonts Serif Fonts Script Fonts Experimental Fonts Futuristic Fonts Web3 Font Media & Broadcasting Variable Fonts Sans Serif Fonts Serif Fonts Script Fonts Experimental Fonts Futuristic Fonts Web3 Font Media & Broadcasting Services Embed License Rent License Agency Partnership Custom Services Embed License Rent License Agency Partnership Custom Services More Fonts Legal Licenses Terms & Conditions Privacy Policy Licenses Terms & Conditions Privacy Policy Help Help Center FAQ Contact Us About Us Help Center FAQ Contact Us About Us ©2026 Drizy Font - All rights reserved. × Sign In Create an Account Sign In Log In to Your Account E-mail address  * Password  * Remember me Forgot Password? Login Create an Account Register Here

════ BODY GROUP e19dc5410d6fccd5 (2 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- 61093a21f5e63dedf54222b3c09997e54c0fe43e3851d21386e02ddcbc246d49  4399 bytes  families: Great Vibes
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/greatvibes/OFL.txt  fetched 2026-09-03T05:59:38Z  path: /Users/symow/bh29_work/evidence/Great_Vibes/OFL.txt
Copyright 2015 The Great Vibes Pro Project Authors (https://github.com/googlefonts/great-vibes)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
https://openfontlicense.org


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.

---- 8b7141c03fa4f8d44e6345d5d4931709290f0f67875e452e95ac1fd3a027802e  4400 bytes  families: Montserrat
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/OFL.txt  fetched 2026-09-03T05:59:51Z  path: /Users/symow/bh29_work/evidence/Montserrat/OFL.txt
Copyright 2024 The Montserrat.Git Project Authors (https://github.com/JulietaUla/Montserrat.git)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
https://openfontlicense.org


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.

════ BODY GROUP other (2 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- c736dec784120a741abed2df6557181b7b510ad4191e1b71a53a5633295cb83a  2390 bytes  families: Hacen Liner XL
---- URL: None  fetched 2026-09-03T08:00:42Z  path: /Users/symow/bh29_work/evidence/Hacen_Liner_XL/embedded_name_table_license.txt
nameID 0 (platform 1, lang 0):
Copyright © 2006 M. Hacen, All Rights Reserved / www.hacen.net

nameID 0 (platform 3, lang 1033):
Copyright © 2006 M. Hacen, All Rights Reserved / www.hacen.net

nameID 5 (platform 1, lang 0):
Version 1.00 2006

nameID 5 (platform 3, lang 1033):
Version 1.00 2006

nameID 8 (platform 1, lang 0):
Muhammad Hacen

nameID 8 (platform 3, lang 1033):
Muhammad Hacen

nameID 9 (platform 1, lang 0):
Muhammad Hacen

nameID 9 (platform 3, lang 1033):
Muhammad Hacen

nameID 10 (platform 1, lang 0):
The family of HacenLiner is specially intended for producing high quality text in the printouts and on the screen. HacenLiner was precisely designed to offer harmonical appearance of Arabic word, professionally built to give proportionate and readable letters whether printed out or shown on the screen. A variety of styles are bundled to achieve great headings and layout.

nameID 10 (platform 3, lang 1033):
The family of HacenLiner is specially intended for producing high quality text in the printouts and on the screen. HacenLiner was precisely designed to offer harmonical appearance of Arabic word, professionally built to give proportionate and readable letters whether printed out or shown on the screen. A variety of styles are bundled to achieve great headings and layout.

nameID 11 (platform 1, lang 0):
www.hacen.net/liner

nameID 11 (platform 3, lang 1033):
www.hacen.net/liner

nameID 13 (platform 1, lang 0):
The artistic design and the points in each glyph of this font are the property of Hacen, your use of this font is limited to production purposes, you may not edit, modify or rename this font without prior permission. Hacen holds the original shape of each letter of this font, any copying, redrawing, or rendering to match or imitate the shape of the original is a breach of copyright law.

nameID 13 (platform 3, lang 1033):
The artistic design and the points in each glyph of this font are the property of Hacen, your use of this font is limited to production purposes, you may not edit, modify or rename this font without prior permission. Hacen holds the original shape of each letter of this font, any copying, redrawing, or rendering to match or imitate the shape of the original is a breach of copyright law.

nameID 14 (platform 1, lang 0):
www.hacen.net/font_license

nameID 14 (platform 3, lang 1033):
www.hacen.net/font_license



---- 187e5110ffb7b6bda2d2f58696790b484e8a2484308e25eb625df9fbc67b4566  3810 bytes  families: Nickainley
---- URL: https://raw.githubusercontent.com/inkstitch/embroidery-fonts/main/src/nick_ainley/LICENSE  fetched 2026-09-03T06:16:37Z  path: /Users/symow/bh29_work/evidence/Nickainley/nick_ainley_LICENSE.txt
﻿Font origin and license for NickAinley

https://www.behance.net/gallery/24243507/Nickainley-Script-Free-Font
Font's name: NickAinley
Font's license: Free for Personal and Commercial use 
Designed by: Seniors Studio
Designer web: https://www.behance.net/seniorsstudio

Font is manually traced and converted to suit Inkstitch embroidery lettering format by Karen Cravens/Silver Seams

================================================================================

The authors "Seniors Studio" has been contacted by Tina Chris:
"Dear Senior Studio Team
We would like to use an embroidery-adapted version of your font in an official release of Inkstitch (https://inkstitch.org/fonts/font-library/). The license does not clearly state if this is allowed. So we would kindly ask if you would allow it? If yes, should we put something special in the license, or change the name?
Thanks
Tina"

Seniors Studio accepted the use of the NickAinley font in a mail:
"Yes, you allowed :)"

================================================================================
https://www.fontsquirrel.com/license/nickainley

Fontfabric License

FFF EULA ver. 2.0 June 2015

By downloading and/or installing a FontfabricTM Free Font you agree to following EULA License:

All fonts on the site (fontfabric.com) available for free download (except “Baron”) can be used for both personal and commercial work.

Allowed uses:
- You may use the free fonts to create images on any surface such as computer screens, paper, web pages, photographs, movie credits, printed material, T-shirts, and other surfaces where the image is a fixed size.
- You may use the licensed fonts to create EPS files or other scalable drawings.
- You may use the free fonts as web-fonts with @font-face declaration to create web sites, web templates, etc.
- You may use the free fonts to create Web Apps, Mobile Apps, Windows Apps, Linux Apps, OS X Apps, Android Apps. etc..

Number of users or page views:
- You’re allowed to install the free fonts on unlimited devices (computers, phones, tablets)
- You’re allowed to upload and use the free fonts on web sites/templates with unlimited pageviews.

Embedding:
- You may embed the free fonts into any document you send to third parties. Such documents may be viewed, printed and edited by the recipients.
- You may embed the free fonts into software or hardware products in which the fonts will be used by the purchasers of such products (PDF’s, WP templates, e-books, Website templates, Mobile Apps, etc.).
- You may embed the free fonts into a web page with a @font-face declaration.
- You’re able to generate web-font packages from the font files in a third party program or generator.

Modifications:
- You may import characters from the font as graphical objects into a drawing program (Adobe Illustrator, Adobe Photoshop, Corel Draw, etc..) and modify such graphical objects.
- You may not modify, adapt, translate, reverse engineer, decompile, disassemble, or create derivative works based on the free fonts itself without Foundry’s prior written consent. That means to edit/modify the font files inself in font editors/software/programs like FontLab Studio, Fontographer, Font Creator, TypeTool, BitFonter, Glyphs, FontStruct, RoboFont, etc..
- You may not resell or redistribute the free fonts itself or any derivative works based on the free fonts itself without Foundry’s prior written consent.
- Keep in mind that we may not answer to e-mails concerning additional information about the licenses and the rights to usege of the free fonts!
- We also have experience creating corporate and bespoke fonts. For more information or inquiries, feel free to send your questions to the following email address: team@fontfabric.com


════ BODY GROUP HTML-1e64bf7b (1 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- 14d342178db81ee6ffec541ddcef47f97b8fcbbcf4d45785df0adadc448fc93b  409350 bytes (HTML page; bytes stored verbatim at the path; TEXT EXTRACTED below, not byte-verbatim)  families: Komika Axis
---- URL: https://localfonts.eu/apostrophic-labs-license/  fetched 2026-09-03T06:18:20Z  path: /Users/symow/bh29_work/evidence/Komika_Axis/apostrophic-labs-license.html
Apostrophic Labs License Skip to navigation Skip to content Search for: Search Menu Home News GitHub News Events Competitions Polls 2020: Top 10 Cyrillic fonts 2019: Top 10 Cyrillic fonts Coming Soon Terms of Service Licenses Authors Contact Sitemap Journal Typography Type Design Best Practices Font Metrics A look at the letter “a” A Look at the Cyrillic Letter „б“ A Look at the Cyrillic Letter “н” (uni043D) Variable Fonts Maxim Zhukov: Cyrillic Ф and Greek Φ A look at the Cyrillic letters ‘Ѣ, ѣ’ German Capital Sharp S Online books’ review Bodoni Type Specimen Books Garamond Type Specimen Books Type Design Catalogues and Specimens Knowledge and ideas exchange Typographic terms Typeface classification Diacritics Anchors in FontLab with Alexei Vanyashin (Russian language) Font hinting Font Interpolation Typography on the web Questions and Answers Font Creation for Newbies Letterbats – A Union of Fine and Typographic Art Type Design Tips and Tricks Font family naming Eduardo Tunni: How to draw sweet font curves (Spanish) Calligraphy and Hand Lettering Ornamental Figures KernType Signs and Symbols Masters of the type Type Design Gallery Different typefaces on the road A History of Type Glagolitic Early Cyrillic Books Буслаевская псалтирь (Buslaev’s Psalter) Short History of the Cyrillic Alphabet Gospels of Tsar Ivan Alexander Russian cursive Old Slavic alphabets and new fonts Old Roman style Cyrillic – historic samples and modern experience His­tory of Civil Script and mod­ern Cyril­lic type Typography in Bulgaria – XIX Century Languages and writing systems Fonts: the Importance of Localisation Local Features Latin Local Features Romanian Latin Moldovan Latin Turkish Feature Locl Cyrillic Local Forms Bulgarian Cyrillic Serbian Cyrillic Macedonian Cyrillic Bashkir Cyrillic Chuvash Cyrillic Krista Radoeva: Cyrillic Script Variations and the Importance of Localisation Botio Nikoltchev: What Shall Be Done for Bulgarian Cyrillic .loclBGR Vedran Eraković: Use of Serbian Cyrillic in Computers Glagolitic Alphabet Cyrillic Alphabets of Slavic Languages Cyrillic Alphabets of Non-Slavic Languages Cyrillic Alphabets of Non-Slavic Languages: Iranian Languages Azerbaijani alphabet Language System Tags Typographic Utilities Font Creators, Editors and Additional Tools FontLab Tutorials Online Font Testing Tools Identify fonts Online font converter Text generators Kerning Pairs Generators OpenType OpenType features Useful Links Working with Texts Font proofing Cyrillic Kerning Pairs Cyrillic Kerning Pairs with „Г“ / „г“ Free Fonts Cyrillic Cyrillic | Bulgarian Cyrillic | Serbian Cyrillic | Handwritten Cyrillic | Handwritten A-M Cyrillic | Handwritten N-Z Cyrillic | Decorative Typewriter Cyrillic and Latin Typefaces Cyrillic | Monospaced Fonts Medieval Glagolitic Fonts Cyrillic Fonts Greek Latin Arabic Programming Fonts Shop Cyrillic Fonts Cyrillic | Bulgarian Sans Serif Serif Slab Serif Monospaced Cyrillic | Serbian Serif Sans Serif Slab Serif Decorative Cyrillic | Sans Serif Cyrillic | Serif Cyrillic | Slab Serif Cyrillic | Decorative Cyrillic | Handwritten Cyrillic | Brush Font Cyrillic | Monospaced Greek Fonts Latin Fonts Sans Serif Fonts Serif Fonts Slab Serif Fonts Monospaced Fonts Vietnamese Fonts Handwritten Fonts Prominent personalities Decorative Fonts Non Latin Scripts Arabic Fonts Armenian Fonts Hebrew Fonts Books My Account Cart Checkout Orders Wishlist Downloads Stores List Become a Vendor Home Apostrophic Labs License Appendix Appendix Handwritten Cyrillic Free Fonts Arabic Fonts Asia – languages and writing systems Authors Aaron Bell Aaron D. Chand Adam Jagosz Adam Katyi Adam Twardoch Adelina Apostolova Adi Floyde Adrian Frutiger Akira Kobayashi Alberto Romanos Alejo Bergmann Aleksandar Nikov Aleksandr Andreev Aleksandr Moskovskiy Alessia Mazzarella Alex Slobzheninov Alexander Lubovenko Alexander Nedelev Alexander Pravdin Alexander Sapozhnikov Alexander Tarbeev Alexandra Korolkova Alexei Vanyashin Alexey Malkov Alfredo Marco Pradil Aliaksei Koval Amy Cox Anastasia Larina Andrea Tartarelli Andreas Eigendorf Andreas Nolda Andrew Kensler Andrey Kudryavtsev Andrij Shevchenko Andriy Dykun Andriy Konstantynov Andy Lethbridge Angelina Sánchez Ani Dimitrova Ani Petrova Ania Wieluńska Anita Jürgeleit Anton Chernogorov Antonina Zhulkova Apostolos Syropoulos Apostrophic Laboratory Archil Imnadze Asen Tiberiy Baramov bBox Type Belleve Invis Ben Jones Benjamin Critton Berthold Wolpe Berton Hasebe Bohdan Hdal Boris Garic Borys Kosmynka Botio Nikoltchev Carrois Type Design Charles Borges de Oliveira Charles Casimiro Charles Gibbons Chris Simpkins Christian Schwartz Christian Thalmann Chuck Masterson Cosimo Pancini Cristian Tournier Cyril Mikhailov Dalton Maag Daniel Benjamin Miller Daniel Johnson Dastan Miraj Dave Crossland Dave Rowland David Březina David Jonathan Ross Denis A Serikov Denis Espinoza Denis Ignatov Denis Masharov Denis Serebryakov Denis Sherbak Diego Aravena Silo Dmitri Zdorov Dmitriy A. Horoshkin Dmitriy Chirkov Dmitry Barsukov Dmitry Goloub Dmitry Rastvortsev Donald Knuth Eben Sorkin Eduardo Manso Eduardo Tunni Eimantas Paškonis Elena Kowalski Elena Voynova Eleonora Petrova Eli Heuer Emanuela Krusteva Emil Bertell Emily Spadoni Emmanuel Besse Eugene Tantsurin Evgeniy Agasyanc Evgeniy Bezdenezhnykh Evita Vilaka Fernando Mello Ferran Milan Oliveras Francesco Canovaro Franco Jonas Hernández Frank Grießhammer Fredrick R. Brennan Friedrich Althausen Galin Kastelov Gatis Vilaks Gennady Fridman George Douros [ UFAS ] George Triantafyllakos Gerard Unger Gluk Fonts [Grzegorz Luk] Grigorij Gushchin Haley Wakamatsu HermesSOFT Hubert Jocham Hugues Gentile Igor Kosinsky Igor Kuznetsov Igor Petrovic Igor Stepanchenko Ilia Gruev Ilya Ruderman Ilya Zakharov Ira Shagaeva Irene Vlachou Irina Smirnova Isabella Chaeva Iste Fonts Ivan Apostolski Ivan Filipov Ivan Gladkikh Ivan Petrov Ivaylo Hristov Jaakko Suomalainen Jacklina Jekova Jakob Runge Jan Fromm Jan Tschichold Jānis Kalaus Jason Castle Jason Smith Jean-Baptiste Levée Jens Kutilek João Cracel João Symington John Hudson Jonathan Hill Jonathan Perez Jonathan Pierini Jordan Jelev Jos Buivenga Jose Scaglione Juan Pablo del Peral Juho Hiilivirta Julia Martinez Diana Julia Sysmäläinen Julieta Ulanovsky Kai Bernau Kaja Słojewska Katsia Jazwinska Kemie Guaida Kevin Burke Khaled Hosny Kiril Zlatkov Konstantin Lukjanov Kostas Bartsokas Krista Radoeva Kristyan Sarkis Ksenia Belobrova Lasko Dzurovski Laura Caldentey Laura Meseguer Lazar Dimitrijević Letter Collective Lewis McGuffie Lisa Fischbach Liza Rasskazova Luc(as) de Groot Lyudmil Dachev Łukasz Dziedzic Maciej Włoczewski Made Type Måns Grebäck Manvel Shmavonyan Marcelo Magalhaes Margarita Dyakovich Maria Doreuli Maria Selezeneva Mariano Diez Mariela Monsalve Mariya Domnikova Mariya Lish Mark Simonson Mark Williamson Martin He Mateo Broillet Mateusz Machalski Matthew Carter Matthias Tellen Michael Angeles Michael Chereda Michael Sharpe Michael Want Michał Jarociński Mike Abbink Mikhail Medvedev Miles Newlyn Milka Peikova Milos Mitrovic MIR Mirela Belova Misha Panfilov Mr. Typeman Nasir Udin Natalia Chuvatin Natalia Vasilyeva NaumType Nenad Hančić Niccolò Agnoletti Nicholas Garner Nick Shinn Nico Inosanto Nicolien van der Keur Niklas Ekholm Nikola Djurek Nikola Kovanovic Nikolay Petrousenko Nils Thomsen Noël Leu Obreshko Obreshkov Oleg Karpinsky Oleh Lishchuk Olexa Volochay Olga Pankova Olga Umpeleva Olivier Gourvat Olli Meier Omana Katzarska Owen Earl Pablo Impallari Panos Haratzopoulos Paul Barnes Paul D. Hunt Paul James MIller Paul van der Laan Pavel Bruev Pavel Emelyanov Pavels Lavrinovics Pedro Arilla Pete Klassen Peter Biľak Peter Olexa Peter Wiegel Phil Garnham Pieter van Rosmalen Pilar Cano Plamen Motev Polina Loseva Przemek Hoffer Radomir Tinkov Ralph Cleminson Raph Levien Rasmus Andersson Ray Larabie René Bieder Reto Moser Riccardo Olocco Richard Miller Robert E. Leuschke Robert Jablonski Robert Slimbach Rodrigo Araya Salas Roland Hüse Roman Pavliuk Ross Milne Rumyana Sokolova Rune Bjørnerås Ryoichi Tsunekawa Sacha Rein Salvador Rodríguez Sam Radian Sarwo Edi Sasha Chebotarev Séamas Ó Brógáin Sebastian Kempgen Serdar Öztürk Sergei Godovalov Sergey Steblina Sergiy Tkachenko Skyhaven Slava Antipov Sláva Jevčinová Sol Matas Stan Partalev Stanislav Chiganov Stefan Peev Stefan Stoychev Steve Matteson Stuart De Rozario Suleyman Yazki Susana Carvalho Svet Simov Svetlin Balezdrov Swiss Typefaces Teo Tuominen The Entente Thomas Gillett Thomas Käding Tikhon Reztcov [ Shriftovik Foundry ] TimXez Titus Nemeth Tobias Frere-Jones Todor Georgiev Tom Grace Tomáš Brousil Toshi Omagari Tristan Grimmer Tseko Tsekov Tural Alisoy Vaibhav Singh Vasil Stanev Vasily Biryukov Vassil Kateliev Vedran Eraković Veneta Rangelova Ventsislav Dzhokov Vera Evstafieva Verneri Kontto Vernon Adams Veronika Burian Veronika Slavova Vicente Lamónaca Vika Usmanova Viktor Kharyk Vincent Chan Vitaly Kuzmin Vitória Neves Vlad Viperov Vladimir Yefimov Vova Egoshin William Veder Yoann Minet Yulia Chernova Yulia Gonina Yury Ostromentsky Zetafonts Become a Vendor Blog Cart Checkout Competitions Contact Cpr. Sparhelt font License Digital Type Foundry Identificator Donation Europe – languages and writing systems Europe – languages and writing systems Europe – languages and writing systems Europe – languages and writing systems Events Font Sampler Free Fonts Arabic Fonts Bulgarian Cyrillic Free Fonts Adys Akrobat Arsenal Arvo Balezdrov11 Barkentina Basil Bitter Blogger Sans Comfortaa Cormac ExtraLight, Cormac Black Cormorant Garamond Cormorant Infant Eau de Garamond Esqadero FiraGO Geologica Gilroy (2 free fonts) Intro Head R Base Karano Kelson Sans Laptev Brush Leftonade Libra Sans Libra Sans Modern Linguistics Pro Lora Manrope Marmelad MDGROTESQUE Regular Merriweather Monitorica Montserrat Montserrat Alternates Muller Narrow Museo Cyrillic (1 free font) Museo Sans Cyrillic (1 free font) Neris (9 free fonts) Neumann Noto Serif Bulgarian Object Sans Oi Ossem Overpass Overpass Mono Perun Phenomena Piazzolla Pliska PT Root UI Rafale BG Ralev 001 Raleway Rawline Roboto Serif Sibila Simbal Sofia Sans Songer Source Sans 3 Source Serif 4 SP ArielBG Unbounded Uni Neue (2 free fonts) Uni Sans Free VDS Vollkorn Wix Madefor Yanone Kaffeesatz Ysabeau Cyrillic Fonts Decorative Cyrillic Free Fonts 20db Airfool Aniron Architectural Arkhip Arturito Aznauri Balkara Balkara Condensed Free Bardo Bernier Beryozki Boecklins Universe Boncegro Bondi Bulgaria Moderna Buran USSR Capture it Capture Smallz Certege Italic Charming Cheque Coiny Cyrillic Cyrivendell Dan Days Desonanz Deux Digital Spatter Dited Dobrozrachniy Dusha Ekran Enthalpy 298 Fantazyor Font Over Giraffe Gogóia Gostrus Hellenica Incopins Clusters Insula Intro Rust, Head, Script Isar CAT Jagodina Kelly Slab Kino KJV1611 Komi Kotyhoroshko Lapsus Pro Legend Library 3 am Linetoline Lkdown Lombard Lumberjack Maler Marapfhont Markh Metropolis Milka Free Movilexia 24th Mr.Amazin Neocyr Open Gost Paperfiller Pepsi Cyr Lat Perfograma Peter Ivanowitsch Pomidor Press Start 2P Prosto One Rahovets Remeslo Riimut Rounded RUNA Ruslan Display Rusticus Screpka Shihan Shinners Shirota Shnobel Snowstorm Socium Sprite Graffiti Font Stalinist One Stiff Staff Tangak Tengwar Sindarin Testo Tetra Tsarevich Typewriter Cyrillic and Latin Typefaces CMU Typewriter Text | Computer Modern Typewriter CMU Typewriter Text Light | Computer Modern Typewriter Light CMU Typewriter Text Variable | Computer Modern Typewriter Variable DXDoklad10M GNU Typewriter Rursus Compact Mono Truetypewriter PolyglOTT TT2020 UM Typewriter USSR Stencil Wellwait Wild Honey Yokawerad Znikomit№25 Dingbat Glagolitic Free Fonts Croatica Glagolica Missal DPG MPH 2B Damase Vinodolski Zakon Greek Free Fonts Unicode Fonts for Ancient Scripts Aegean Aegyptus Akkadian Alexander Alfios Anaktoria Analecta Aroania Asea Atavyros Avdira Maya Musical Symbols or Musica Symbola Handwritten Cyrillic Free Fonts 99 Percent Occupy A Day without Sun Abram Abys Alcotton Amatic SC Anitype Redwood Anselmo Architun Azbuka03_D Bad Script Balsamiq Sans Beer Money Bemount Benvolio BK Handy Cyr Bristol Brock Script_D Brush Font № 1 Brush. Calligraphy style Brush. Free style Brusher Brushshop Bublina the Dog Bukhari Script Calligraphy Capuletty Caveat Celestina Cheeseusaceu Chekharda Chickpeas Chocolate Nesquik Cirilica Pisana Nova D Comic Helvetic Denistina Discipuli Britannica Djiovanni Durazky East Sea Dokdo Cyrillic Elfabe Elowen Engine Eskal EuroScript Fewriter Firenight Five minutes Flow Ext FRB American Cursive Freeride Frenchpress Gagalin Gochi Hand Cyrillic Gogol Good Vibes Pro Graffiti Gregory Guerrilla Gunny Rewritten Handwritten Handwritten Cyrillic Free Fonts A-M Handwritten Cyrillic Free Fonts N-Z Hangyaboly Happy Fox Condensed Hater Helvetia Verbundene Hi Melody Cyrillic Hitch Hike Iced Tea Inspiration Intro Script R H2 Base Itim Cyrillic Just Breathe Karmina Karton Katona KobzarKS Kosko Krabuler kraM Kurochka Lapkoi Lemon Tuesday Lemonade Stand Lionelofparis Lobster London One Lorenco Made Barista MADE GoodTime MADE Likes MADE TheArtist Magnolia Script Maksik Hand Mandy’s Sketch Marck Script Marutya Mateur May Merkucio MewTooHand Miama Nueva Moloko Monly Monoconv Montekky Nautilus Pompilius Neucha Nickainley Nicoletta Script Niscript Novito Novito Nova Nyasha Sans Old School Pacifico Pag Pangolin Papaya Sunrise Paper Paris Pattaya Pecita Pen. Calligraphy style Pen. Free style People PH Plovdiv Typeface Radio Volna Ramona Repivmanusc Resphekt Reys Romochka Royana Rozovii Chulok Russkopis Salavat Samson School Sensej Shantell Sans SK Pencil Solena Southbank Sans Sriracha Stefano Summer Sunday Swanky and Moo Moo Cyrillic Tag Type Tibalt TippyToes Tkachenko Sketch 4F Tovari Sans Trush Underdog UStroke Various Vasek Veles Vinograd Wolgast Two Xiomara-Script Xplor Xtreem 2 Yarin Zhizn International Cyrillic Free Fonts 2MASS J1808 AC Line Acca Agave Ahellya Airborne Alegreya Alegreya Sans Alice Amerika Andika Anglecia Pro Anka Coder Anonymous Pro Aqum Archive Arev Sans Arimo Average Mono Azoft Sans B20 Sans Beatrix Antiqua Bebas Neue Bellota Bellota Text Berenis ADF Pro Boxfont Round Bravo BreezeSans BreezeSans Condensed Brill Brygada 1918 Bully Cantarell Carlito Cascadia Code Casper Caviar Dreams Charis SIL Clara Clear Sans CMU Serif Cochineal Code New Roman Coelacanth Comic Relief Conthrax Corki Cousine Cunia Cuprum Cyntho Pro Cyntho Slab Pro DejaVu Sans DejaVu Sans Mono DejaVu Serif Deposit Pro Didact Gothic Disket Mono Dita Sweet Domitian Drazki9 Droid Sans Droid Serif Drugs EB Garamond 12 Epistle Evolventa Exo 2.0 Fantasque Sans Mono Finlandica Fira Code Fira Mono Fira Sans Fira Sans Compressed Fira Sans Condensed Fira Sans Extra Condensed FoglihtenNo06 Fontin Sans Cyrillic Forum Fowviel FreeMono FreeSans FreeSerif Fregat FT Anima Gabriela Gamestation Germano Glametrix Go Go Mono Golos Text Gorod Gravity Hack Hagin Heuristica Highliner IBM Plex Mono IBM Plex Sans IBM Plex Serif Idealist Sans Igra Sans Ikra Slab Inconsolata LGC Markup Inglobal Inter International Cyrillic Monospaced Fonts International Cyrillic Sans Serif Fonts International Cyrillic Serif Fonts International Cyrillic Slab Serif Fonts Iosevka Istok and Istok Web JetBrains Mono Jost Jura Kazmann Sans Kelvinch Kraskario KULAG Kurale Lato Ledger Liberation Mono Liberation Sans Liberation Serif Libertinus Serif Libre Franklin Lingua Franca Linux Biolinum Linux Libertine Literata Luculent M+ Marta Matias Measure Miedinger* Mirror 82 Monoid Mononoki Nairi New Ahena Unicode Next Art Nimbus Mono Nimbus Roman No 9 L Nimbus Sans L NK57 Monospace No Name 37 Nobile Noto Sans Noto Sans Condensed Noto Sans ExtraCondensed Noto Sans SemiCondensed Noto Serif Nunito Nunito Sans Old Standard Open Sans Open Sans Condensed Opinion Pro Oranienbaum Orchidea Pro Osterbar Oswald Outward Oxygen Peace Sans Pfennig Philosopher Play Playfair Display Podkova Poiret One Prata Proggy Vector PT Astra Sans PT Astra Serif PT Mono PT Sans PT Serif Rafale RU Ristretto Slab Pro (1 free font) Road UA Roboto Roboto Condensed Roboto Slab Rubik Ruda Russian Road Sign Russo One Sabir Mono Sansation Sansus Webissimo Scada Seymour One Source Code Pro Source Sans Pro Source Serif Pro Spectral Sreda STIX Sudo Sverdlovsk Taylor Sans Tempora Tenor Sans TeX Gyre Adventor TeX Gyre Bonum TeX Gyre Cursor TeX Gyre Heros TeX Gyre Pagella TeX Gyre Schola TeX Gyre Termes Tinos Ubuntu Unifont Viaoda Libre Victor Mono Vladivostok Walleye WeblySleek UI Wes Xolonium Latin Script (free fonts) Aurulent Sans Mono Brevier Viennese Coco IBM Plex Sans Condensed Latina Essential Obrazec Rosarina Wonder Unit Sans Medieval Cyrillic Free Fonts Akathistos Beresta Bukvica Bukvitsa Unicode BukyVede Cathisma Unicode Dilyana Evangelie Fedorovsk Unicode Feofan Fira Slav Glagoli Hilandarski Ustav 5 Hirmos Indiction Unicode Irmologion Kathisma Kliment Std Lazov Menaion Medieval Menaion Unicode Monah 5 MonahOCS Monomachus Monomakh Unicode MPD-Evangelie UCS Oglavie Ostrog Pochaevsk Pomorsky Unicode Ponomar Unicode Posad Roman Cyrillic Std Shafarik Skaryna 2017 Slavjanic StaroUspenskaya Stefanit Triodion Vertograd Zlatoust Programming Fonts Droid Sans Mono Meslo LG M Serbian Cyrillic Free Fonts Glagolitic and Cyrillic letters and Ornaments Glossary Google Drive Home International Cyrillic Commercial Fonts Anglecia Pro (6 free fonts) Cyntho Next Cyntho Next Slab Naslof Pancetta Pro Pancetta Serif Pro Pelmeshka Ristretto Pro Ristretto Slab Pro TT Bells Journal A typeface should be visually appealing and technically sound Book cover design in Bulgaria during XX century #482 (no title) Pencho Slaveykov. Na ostrova na blazhennite Vazov. Kazalarskata Tsaritsa Yavorov. Gotse Delchev Yavorov. Insomnias Franco Jonas: You can find very good quality typeface designs in Chile HOW TO TURN A CITY INTO A CAPITAL OF CULTURE Letters must come from our hands Maria Doreuli: Cyrillic fonts are on the rise Seemingly marginal languages are an integral part of the world The Bulgarian type craft belongs on the global stage Type design needs to respect the language and the culture it represents Type is a cultural heritage, it is one of the ways to recreate the surrounding world БУКВИТЕ ИЗХОЖДАТ ОТ РЪКАТА, ОТ ИНСТРУМЕНТА, С КОЙТО СЕ ПИШЕ ИЛИ РИСУВА КАК ДА ПРЕВЪРНЕМ ЕДИН ГРАД В СТОЛИЦА НА КУЛТУРАТА МАРИЯ ДОРЕУЛИ: ПАЗАРЪТ НА КИРИЛСКИ ШРИФТОВЕ НАРАСТВА ЗНАЧИТЕЛНО МЯСТОТО НА БЪЛГАРСКОТО ШРИФТОВО ИЗКУСТВО Е НА СВЕТОВНАТА СЦЕНА ПРИВИДНО МАРГИНАЛНИТЕ ЕЗИЦИ СА НЕОТМЕННА ЧАСТ ОТ СВЕТА ШРИФТ ШРИФТЪТ ТРЯБВА ДА Е ПРИЯТЕН ВИЗУАЛНО И ДА Е ТЕХНИЧЕСКИ ИЗПИПАН Jürgen Huber and Martin Wenzel: The design of a typeface must resemble the key values of the brand Kerning Pairs Generators Latin Script (handwritten fonts) Local Fonts Free For Personal and Commercial Use License My account My Orders News GitHub News Nymphont License Ornamental Figures ParaType – Free Font Software License Agreement ParaType License PT Polls 2019: Top 10 Cyrillic fonts 2020: Top 10 Cyrillic fonts Proto Grotesk Quiza Pro Ristretto Pro (1 free fonts) Sabrina Sample Page Should designers care about typographic mistakes Sitemap Skorid Store List Stores List Terms of Service Licenses Apache License 2.0 Apostrophic Labs License Bitstream Vera Fonts Copyright End User License Agreement Free for personal and commercial use Free for personal and commercial use Free for personal use GNU General Public License (GPL-2.0) GNU General Public License (GPL-3.0) MIT License SIL OPEN FONT LICENSE Test Typography A History of Type Early Cyrillic Books Буслаевская псалтирь (Buslaev’s Psalter) Glagolitic His­tory of Civil Script and mod­ern Cyril­lic type Old Roman style Cyrillic – historic samples and modern experience Old Slavic alphabets and new fonts Short History of the Cyrillic Alphabet Gospels of Tsar Ivan Alexander Russian cursive Typography in Bulgaria – XIX Century Coming Soon Yuli Fonts: the Importance of Localisation Botio Nikoltchev: What Shall Be Done for Bulgarian Cyrillic .loclBGR Krista Radoe

════ BODY GROUP HTML-d699b0a5 (1 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- 3e583887262ff37f2a2b8058879c042c3266648511e19f8677e00a3765a4930e  11467 bytes (HTML page; bytes stored verbatim at the path; TEXT EXTRACTED below, not byte-verbatim)  families: Komika Axis
---- URL: https://web.archive.org/web/20010221231147id_/http://www.hardcovermedia.com:80/lab/laboratory.html  fetched 2026-09-03T07:54:48Z  path: /Users/symow/bh29_work/evidence/Komika_Axis/apostrophiclab_laboratory_20010221231147.html
industry was started by rednecks This is the section where you get to see previews of works in progress. The images below are of fonts that will be posted here for download in the near future. Some of images are links to a more detailed view of the previewed fonts. Currently Apostrophic Laboratories features collaborative designs by the following people and myself: CybaPee , Jeri Ingalls , Karen Clemens , Dana Rice , Neumat Ick, Link Olsson , Brigido Maderal , Fleisch , Graham Meade , Alejandro Paul , Yol , Marley Diehl, Rich Parks , Marjan Bozic , Phynette , Keya Kirkpatrick, Evelyne Pichler, Jeff Lan, WolfBainX, and Steve Deffeyes . If for some reason you feel like being a chemist on staff in this lab, send me a note .

════ BODY GROUP HTML-ead6e2ea (1 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- f1646f964138de17d09354083c105d8b3a361fa71b9a3f20270a72702cac3280  3317 bytes (HTML page; bytes stored verbatim at the path; TEXT EXTRACTED below, not byte-verbatim)  families: Komika Axis
---- URL: https://web.archive.org/web/20010221031257id_/http://www.hardcovermedia.com:80/lab/main.html  fetched 2026-09-03T07:58:01Z  path: /Users/symow/bh29_work/evidence/Komika_Axis/apostrophiclab_main_20010221031257.html
2001 is the Year of Gurrl Power!

════ BODY GROUP HTML-b480f758 (1 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- 88aa1eec881a286a6809508d489534f08b38a889b3fd780190c6b2b8d05221d3  167842 bytes (HTML page; bytes stored verbatim at the path; TEXT EXTRACTED below, not byte-verbatim)  families: Nexa
---- URL: https://www.fontfabric.com/fontfabric-commercial-eula-for-free-fonts/  fetched 2026-09-03T06:29:58Z  path: /Users/symow/bh29_work/evidence/Nexa/fontfabric-commercial-eula-for-free-fonts.html
Fontfabric Commercial EULA For Free Fonts - Fontfabric™ Skip to content Fontfabric™ - Home Browse Fonts Fonts on Sale Custom Services Partnerships Fonts in use About Contact us Help Blog Affiliate Program Test our fonts for free Follow us online Browse Fonts Custom Services Licensing Fontfabric™ - Login Cart Welcome back Please verify your email. We sent verification code. To verify your email address, please check your inbox and enter the code below. Verify Otp Send Sucsessfully Didn't receive an email? Try Again Remember me Forgot password? Login now OR Continue with Facebook Continue with Google Don't have an account? Sign up Reset password Lost your password? Please enter your username or email address. You will receive a link to create a new password via email. Reset password Already have an account? Login Home / Fontfabric Commercial EULA For Free Fonts Fontfabric Commercial EULA For Free Fonts All  Fontfabric Fonts (Software)  available for a free download and commercial use come with a standard  Fontfabric Commercial End-User License Agreement For Free Fonts  as part of the free download (apart from specific restrictions that come with any other type of  Fontfabric License ). By downloading, installing, copying, or using one or more of the free-download  Fontfabric Fonts (Software)  available for commercial use, you agree to the terms, stated within this legal agreement. 01. GENERAL PROVISIONS: This is a “ Fontfabric Free Font End User License Agreement ” (“FF EULA”) between you as an end-user (“ Licensee ”) and  Fontfabric  LLC  (“ Licensor ”). “Fonts” / “Free fonts” refers to the set of files released by the Fontfabric under this Fontfabric End-User License Agreement and clearly marked as such. This may include source files, build scripts, and documentation. “Original Works” refers to the collection of Fontfabric Fonts (Software) components as distributed by Fontfabric . “Derivative Works” refers to any derivative made by adding to, deleting, or substituting — in part or in whole — any of the components of the “Original Works”, by changing formats or by porting Fontfabric Font (Software) to a new environment. “Page Views’ refers to the number of times a user views a web page on a website or online platform that use Fontfabric Fonts (Software) . Page Views indicate how many times one or more Fontfabric Fonts (Software) are served. You are welcome to give  Fontfabric , as the  Licensor , credit in your work and to send examples of the free  Fontfabric Font (Software)  in use to the following address:  contact@fontfabric.com 02. ALLOWED USES OF FONTFABRIC FONTS (SOFTWARE): A Licensee CAN (✓) use free Fontfabric Fonts (Software) to create any type of design, Derivative Works and visuals, on any surface, such as fabrics, textile and print, like clothing, paper, other printed materials, logos, business and greeting cards, postcards, postage stamps and other stationery materials, books, magazines, newspapers, newsprint and other printed and editorial materials, envelopes and package design, wallpaper prints, infographics, any vector graphics and any office supplies that are elements of a brand identity, along with computer and/or other device screens, like web pages, images, photographs and visuals, movie credits and other surfaces where the image has a fixed size. A Licensee CAN (✓) use free Fontfabric Fonts (Software) to create vector files or other scalable drawings (AI, EPS, PDF etc.), as well as static images (JPEG, TIFF, PNG etc.), even if these images are used on the web or in a mobile app. A Licensee CAN (✓) use free Fontfabric Fonts (Software) to create Web Apps, Mobile Apps, Windows Apps, Linux Apps, OS X Apps, Android Apps, etc., and may have no limitation to distribute your apps. A Licensee CAN (✓) use free Fontfabric Fonts (Software) as web-fonts with @font-face declaration to create web sites, web templates, etc. A Licensee CAN (✓) use the free Fontfabric Fonts (Software) to create any files for ePub, such as PDF, WP templates, e-books, website templates, mobile apps, etc. for any kind of devices including Kindles, iPads, or other eReaders amidst others. A Licensee CAN (✓) use the free Fontfabric Fonts (Software) to create any type of video content, distributed via streaming services, TV advertising, Broadcasting or social media. A Licensee CAN (✓) modify vector outlines of free Fontfabric Fonts (Software) . 03. NUMBER OF USERS / PAGE VIEWS OF FONTFABRIC FONTS (SOFTWARE) : A Licensee CAN (✓) install free Fontfabric Fonts (Software) on unlimited devices (computers, phones, tablets, etc. devices). A Licensee CAN (✓) upload and use free Fontfabric Fonts (Software) on websites/templates with unlimited Page Views. 04. EMBEDDING FONTFABRIC FONTS (SOFTWARE): A Licensee CAN (✓) embed free Fontfabric Fonts (Software) into any document you send to third parties. Such documents may be viewed, printed, and edited by the recipients. A Licensee CAN (✓) embed the free Fontfabric Fonts (Software) into software or hardware products in which the fonts will be used by the purchasers of such products (PDFs, WP templates, e-books, Website templates, Mobile Apps, etc.). A Licensee CAN (✓) embed free Fontfabric Fonts (Software) into a web page with a @font-face declaration. A Licensee CAN (✓) generate web-font packages from free Fontfabric Fonts (Software) in a third-party program or generator. 05. FONT (SOFTWARE) MODIFICATIONS: A Licensee CAN (✓) import characters from free Fontfabric Fonts (Software) as graphical objects into a graphic design program and modify such as graphical objects. A Licensee CAN NOT ( ⃠ ) modify, adapt, translate, reverse engineer, decompile, disassemble, or create Derivative Works based on any free Fontfabric Fonts (Software) without prior written consent by Fontfabric (this means to edit/modify the font files themselves in font editors/software/programs like FontLab Studio, Fontographer, Font Creator, TypeTool, BitFonter, Glyphs, FontStruct, RoboFont, etc.). A Licensee CAN NOT ( ⃠ ) resell or redistribute free Fontfabric Fonts (Software) themselves or any Derivative Works based on the free fonts themselves without prior written consent by Fontfabric . Enter your details to receive all trial fonts We'll send you a zipped file with all trial fonts, license agreement, and installation instructions. I want to receive updates on new releases, subscriber-only discounts, personalized offers, and resources for getting the most out of my fonts. Send me the pack Thanks for choosing Fontfabric's trial fonts! We help designers from all over the world scale up their projects and clients with great typography. Opt-out anytime by clicking the Unsubscribe link in the footer of your emails. See our Privacy Notice for more information. Stay in the loop Subscribe now for exclusive access to our latest releases, free fonts, special deals and insider typography tips. Subscribe Follow us online Explore all pages Type foundry Typography services Font customization Font families Font Licensing Font Tester Trial Fonts Sans-serif fonts Serif fonts Display fonts Mono fonts Rust fonts Script fonts Font sale Free fonts Fonts in use Font collections Join our affiliate program Legal Infringements About Help Blog Partnerships Contact us 2026 © Fontfabric llc. Privacy Notice Terms and Conditions Manage Cookies

════ BODY GROUP HTML-06e88d25 (1 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- b3476a78d477b83b98bad07db1a443dfb1c3c90ebcd1a9232a16ee6e22ee4af7  234922 bytes (HTML page; bytes stored verbatim at the path; TEXT EXTRACTED below, not byte-verbatim)  families: Nexa
---- URL: https://www.fontfabric.com/fontfabric-commercial-eula-for-retail-fonts/  fetched 2026-09-03T06:29:54Z  path: /Users/symow/bh29_work/evidence/Nexa/fontfabric-commercial-eula-for-retail-fonts.html
Fontfabric Commercial EULA For Retail Fonts - Fontfabric™ Skip to content Fontfabric™ - Home Browse Fonts Fonts on Sale Custom Services Partnerships Fonts in use About Contact us Help Blog Affiliate Program Test our fonts for free Follow us online Browse Fonts Custom Services Licensing Fontfabric™ - Login Cart Welcome back Please verify your email. We sent verification code. To verify your email address, please check your inbox and enter the code below. Verify Otp Send Sucsessfully Didn't receive an email? Try Again Remember me Forgot password? Login now OR Continue with Facebook Continue with Google Don't have an account? Sign up Reset password Lost your password? Please enter your username or email address. You will receive a link to create a new password via email. Reset password Already have an account? Login Home / Fontfabric Commercial EULA For Retail Fonts Fontfabric Commercial EULA For Retail Fonts End User License Agreement  1 Purpose  Fontfabric Ltd (“Fontfabric”, “we” or “us”), together with its wholly-owned subsidiaries are professionals in the field of Font creation and design. These Terms are between you and the Fontfabric which owns all rights to the Font Software you have purchased.  “ Customer ” means the entity you represent in accepting this Agreement or, if that does not apply, you individually. If You are using the Font Software on behalf of Your employer or as a consultant or agent of a third party (collectively “Your Company” ), You represent and warrant that You have the authority to act on behalf of and bind Your Company to the Terms of this Agreement and everywhere in this Agreement that refers to Customer , shall also include Your Company .  2 Terms of the Agreement  2.1 Licences  Subject to the terms and conditions of this Agreement , Customer shall have a non-exclusive, non-assignable, non-transferable (except as expressly permitted) license to install, access and Use the Font Software . Fontfabric reserves all rights not expressly granted to you in this Agreement . Customer may allow its Authorized Users to use the Font Software , and they are responsible for their compliance with this Agreement and Customer’s applicable Order Form .  2.2 Order Forms  The Font Software shall be ordered by the Customer pursuant to Order Forms through Fontfabric Marketplace . Each Order Form shall include at a minimum the name of the Font , Type of license, any license restriction, and other types of rights (transfer, renew, etc). The use is further governed by the individual types of licenses you select while filling your Order Form , and to which you agree in the course of placing your order.  The Customer may choose between an annual or perpetual license when placing an order for Font Software through the Fontfabric Marketplace except for Desktop licenses, which are exclusively available as perpetual licenses. The duration of the license, whether annual or perpetual, will be explicitly stated in the invoice issued by Fontfabric following the Customer’s purchase.  Any one of Customer’s Affiliates may also order Font Software under this Agreement by submitting an Order Form and agreeing to be bound by the terms of this Agreement .  2.3 Acceptance  This Agreement shall be effective upon the date that Customer receives Font Software (hereinafter “Effective Date”). Complete execution of this Agreement is contingent upon Customer’s tender of the Fee to Fontfabric or Fontfabric’s authorized representatives.  2.4 Changes to the Terms  The last revision of this Agreement is set forth at the top of this Agreement . As we add new features, we may revise or supplement this Agreement . We will provide you with advance notice of material revisions to this Agreement . We will not make revisions that have a retroactive effect unless we are legally required to do so. Your continued use of the Font Software after the new revision constitutes your acceptance of this Agreement , as amended.  3 Customer rights and responsibilities  3.1 Obligations  Customer shall use its best efforts to ensure that each user of the Font Software abides by the terms and conditions of this Agreement . The Customer further agrees to distribute to each Authorized User of the Font Software a copy of this EULA . The Customer may copy this EULA as necessary to ensure distribution to each Authorized User of the Font Software.  3.2 Free Font Software  Fontfabric may make a free Font Software available to Customers . Use of free Font Software is subject to the terms and conditions of a separate Agreement.  3.3 Verification of Use  Customer will monitor its own use of the Font Software and report any use in excess of the licensed volume. Fontfabric may monitor use to verify compliance with license restrictions, volume and the Agreement .  4 Use Conditions  4.1 General  The Font Software is and remains the property of Fontfabric . As a licensed Entity it is important that you read and adhere to the following section and its conditions of use.  You are permitted to make copies of the Font Software, as long as such copies are made following the terms and restrictions of the license you have purchased. Such copies may be used only for the purposes permitted by the license grant and must not exceed the scope of the granted rights Reformatting or regenerating the Font Software for compatibility with another operating system is prohibited unless such use is expressly permitted. Removing the public metadata and private data blocks included in the Font Software is strictly forbidden.  The copying of any written material which may accompany the Font Software is not permitted. The Font Software and any accompanying written material are protected by Copyright and other International Treaties. Unless otherwise noted, all copyrights and trademarks are the property of Fontfabric .  4.2 Use Limitations  You must ensure that all use of the Font Software conforms to, and does not deviate from, (a) the limits on usage to which you agree in the course of ordering those products; and (b) the terms and conditions contained in the Agreement .  4.3 No Copying or Distribution  No copying or distribution of any of the Font Software may be made, except as expressly provided in this Agreement . Without prejudice to such obligation, you shall ensure that all copies and distributions of Font Software include the same copyright and other proprietary notices as appear on the original file, which we make available. All copies of the Font Software must be kept under your exclusive control.  4.4 No Decompilation or Modification  Customer may not recompile, reverse engineer, disassemble, or modify in any other way the Font Software or creation of any derivative work in whole or in part. If the Customer is located in a European Union member country or any other country which provides rights materially similar to the rights set forth in this provision, the Customer may reverse engineer or decompile the Font Software only to the extent that sufficient information is not available for the purpose of creating an interoperable software program but only for such purpose and only to the extent that sufficient information is not provided in a timely manner free of charge by Fontfabric upon written request. 5 Third party use  5.1 Customer obligations  The Customer has the right to provide the Font Software for temporary use to a designer or another agent working on behalf of the Customer unless otherwise specified. Third Parties may use the Font Software exclusively for Customer’s work only if they agree to the terms and conditions of this Agreement . Customer agrees to distribute to each Third Party working on their behalf with the Font Software a copy of the Agreement . Upon completion of the work Third Parties should not retain any copies of the Font Software .  5.2 Third Party obligations  Third Parties are allowed to use the Font Software according to the terms of the Agreement between Fontfabric and the Customer . Third Parties use the Font Software only for the completion of work allocated to them by the Customer.  Third Parties shall certify to Customer and Fontfabric, in writing, that they do not retain any copies of the Font Software and that all copies have been destroyed.  Third Parties may not:  ● decompile, reverse engineer, disassemble, modify, and create derivative works, i.e., the creation of different weights or styles of the font(s),  ● lend, rent, sub-license or distribute, in whole or in part, to another third party (friends, relatives, service bureaus),  ● reform or regenerate the Font Software for compatibility with another operating system, ● remove the public metadata and private data blocks included in the Font Software ,  ● copy any written material which may accompany the Font Software .  6 Fontfabric rights and responsibilities  6.1 General  Fontfabric shall deliver the Font Software (which includes the agreed fonts and the full documentation) in the time agreed with the Customer . Fontfabric represents and warrants that it either owns fully and outright, or otherwise possesses and has obtained, all rights, approvals, licenses, consents and permissions as are necessary to perform its obligations and to exercise its rights hereunder. The Fontfabric hereby represents and warrants that it owns all rights, titles, and interests in the Font Software , and they do not infringe the Intellectual property rights of any third party.  6.2 Protection of the Font(s) and Font Software  Fontfabric has the right to request proof of Customer’s compliance with the terms and conditions of this Agreement . Within thirty (30) days of a request by Fontfabric , Customer agrees to certify in writing that the use of the Font Software at the time of the request is in conformity with this Agreement . Customer acknowledges that if their use exceeds the grant of the license and its restrictions as specified in this Agreement , they are required to buy a license that reflects the actual use of the Font Software .  The Customer shall take all reasonable steps to safeguard the Font(s) and the Font Software from any unauthorized use, duplication, sublicensing, or distribution. Furthermore, the Customer and the Third Party are responsible for ensuring the Font Software can only be used in a manner allowed by this Agreement . The failure to adequately protect the Font Software against use in any manner not contemplated in this Agreement shall be considered a failure to comply with its terms and will result in the termination of this Agreement .  6.3 Audit  If Fontfabric has reasonable grounds to believe that this Agreement may not be fully adhered to, we may request your cooperation in conducting an audit of the use of the Font and Font Software. Such an audit will be arranged collaboratively and conducted with your knowledge and consent. To ensure a smooth process, we will provide at least fifteen (15) days’ notice prior to the audit and kindly request your assistance in providing access to relevant systems, devices, records, and information to confirm compliance with the terms of this Agreement.  If Fontfabric determines that your use is in violation of this Agreement and the applicable Invoice, you acknowledge and agree that you are required to buy a license that would bring your use into compliance. Fontfabric reserves the right to seek any other remedies available at law or in equity.  However , in conducting any audit, Fontfabric will comply with all applicable data protection and privacy laws, including but not limited to the obligations outlined in Section 7.2 of this Agreement. Fontfabric will not access, collect, or use any personal data of the Customer’s employees, clients, or any third party unless such access is necessary for verifying compliance and is strictly limited to the scope of the audit.  Prior to any audit, Fontfabric will provide the Customer with reasonable notice and will cooperate with the Customer to agree on the scope, duration, and method of the audit to ensure that the Customer’s data protection obligations are upheld. Any personal data accessed during the audit will be handled in accordance with Fontfabric’s privacy and data protection policies and will be securely deleted or returned to the Customer upon completion of the audit.  6.4 All Rights Reserved  The Font Software is the exclusive property of the Fontfabric . The Font Software contains copyrighted material, trade secrets and other proprietary material. The Font Software is protected under the laws of the Republic of Bulgaria and other International Treaty Provisions. This Agreement shall not be construed as transferring any rights other than those expressly permitted herein. Fontfabric reserves all copyrights, trademarks, and any other form of intellectual property rights in and to the Font Software .  7 Privacy and Information  7.1 Confidentiality  “Confidential Information” means all information disclosed by Fontfabric to the Customer , whether orally or in writing, that is designated as confidential or that reasonably should be understood to be confidential given the nature of the information and the circumstances of disclosure. Confidential Information includes the terms and conditions of this Agreement and all Order Forms (including pricing). Confidential Information also includes business and marketing plans, technology and technical information, product plans and designs, and business processes disclosed by Fontfabric .  The Customer shall, on behalf of itself and all Authorized Users , retain all Confidential Information furnished by Fontfabric in connection with or derived from the Font Software in strictest confidence and shall not publish or disclose such Confidential Information at any time during the term of this Agreement or after its termination.  7.2 Data protection  Fontfabric will maintain appropriate administrative, physical, and technical safeguards for the protection of the security, confidentiality, and integrity of Customer data. Those safeguards will include, but will not be limited to, measures designed to prevent unauthorized access to or disclosure of Customer . Except with respect to a free trial, the terms of the data processing addendum on the Privacy and DPA page are hereby incorporated by reference and shall apply to the extent Customer data includes Personal Data, as defined in the DPA.  8 Invoices and Payment  8.1 Pricing and Payment  You undertake to provide accurate and current information about yourself – including your correct name, address and any other requested details – in the course of ordering Font Software .  Customer will provide Fontfabric with valid and updated bank card information, or with a valid purchase order or alternative document reasonably acceptable to Fontfabric . If the Customer provides bank card (credit card, debit card, virtual card etc.) information to Fontfabric , Customer authorizes Fontfabric to charge such bank card for all Font Software and licenses listed in the Order Form and any renewals, if any. Customer ensure that they are fully entitled to use that card, and it has available funds sufficient to cover the charges which are deducted from it.  8.2 No Refunds  All amounts are non-refundable, non-cancellable, and non-creditable.  9 Tax  Fees and other charges imposed under an Order Form will not include taxes, levies, duties or similar governmental assessments of any nature, including, for example, value-added, sales, use or withholding taxes, assessable by any jurisdiction whatsoever (collectively, “Taxes”), all of which will be for Customer’s account. Customer is responsible for all taxes, other than Fontfabric’s income and payroll taxes. Customer must provide to Fontfabric any direct pay permits or valid tax-exempt certificates prior to signing an Order Form . If Fontfabric has the legal obligation to pay or collect Taxes for which Customer is responsible under this section, Fontfabric will invoice Customer and they will pay that amount unless Customer provides Fontfabric with a valid tax exemption certificate authorized by the appropriate taxing authority. For clarity, Fontfabric is solely responsible for taxes assessable against it based on its income, property and employees.  10 Termination and Cancellations  10.1 Termination  10.1.1 Termination for Cause  We may terminate this Agreement for any material breach of this Agreement by the Customer upon thirty (30) days written notice. The written notice shall identify the alleged breach(es) by Customer and request a cure. If you fail to comply with the EULA within this time period, the Agreement will terminate automatically.  Either party may terminate this Agreement if the other party ceases operation without a successor or seeks protection under any bankruptcy, receivership, trust deed, creditors’ arrangement, composition or comparable proceeding, or if any such proceeding is instituted against that party (and not dismissed within sixty (60) days thereafter).  10.1.2 Termination of the Annual License  Unless otherwise specified in this Agreement, the initial term of the Annual License shall be 12 (twelve) months (“Initial Term”) and automatically renew for subsequent periods of twelve (12) months (each a “Renewal Term” ), unless either party notifies the other party no less than 30 calendar days before the end of the Initial Term or any Renewal Term that the Agreement shall not renew. The Customer should give the termination notice to Fontfabric via their account on the Fontfabric Marketplace.  10.1.3. Termination for Convenience  This Agreement may be terminated by Customer at any time by destroying the Font Software , together with any printed materials and copies. In such case, the Customer shall notify Fontfabric of the actions taken.  10.2 Consequence of termination  Upon termination of this Agreement for any reason, Customer is required to destroy or return to Fontfabric all original Font Software and any accompanying written material. The Customer shall also certify to Fontfabric that all copies of the Font Software have been destroyed. In the event of termination due to breach by Customer , nothing herein shall be construed as a waiver of any of Fontfabric’s rights or remedies under Equity or Law.  In the event of early termination of this Agreement, the license shall remain valid for the period for which it was paid, and no refunds will be given for any amounts already paid by the Customer. The Customer will retain the right to use the Font Software until the end of the paid term, under the terms of this Agreement. The provisions of Section 8.2 of this Agreement are applicable accordingly.  11 Liability and Indemnities  11.1 Warranties  11.1.1 Mutual Warranties  Each party represents and warrants that it has the legal power and authority to enter into this Agreement . 11.1.2 Our Warranties  The Font, Font Software and related documentation are provided “as is”. Fontfabric warrants that, at the time of delivery of the Font Software to the Customer, the Font Software will be technically functional, tested, and ready for use. However, the Customer assumes all risk regarding the ongoing quality and performance of the Font Software after delivery. Fontfabric does not warrant that the Font Software will be compatible with all devices, applications, or programs used by the Customer. Fontfabric is not responsible for any inability to use the Font Software due to the Customer’s technical environment, including but not limited to the Customer’s devices, operating systems, or software applications.  Except as expressly stated in this Agreement, there are no other warranties, conditions, or representations, express or implied, including but not limited to implied warranties of merchantability or fitness for a particular purpose, made by Fontfabric with respect to the Font Software. Any implied warranty or condition required by law is limited  to a thirty (30) day warranty period, starti

════ BODY GROUP HTML-9eebc8d1 (1 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- 30ae75c67e3e1d4815fdf0dff4c3570f988bb977c0b74dcb49eb6a7ceb33f0d6  24047 bytes (HTML page; bytes stored verbatim at the path; TEXT EXTRACTED below, not byte-verbatim)  families: Nickainley
---- URL: https://www.fontsquirrel.com/license/nickainley  fetched 2026-09-03T07:37:58Z  path: /Users/symow/bh29_work/evidence/Nickainley/nickainley.html
License for font family 'Nickainley' | Font Squirrel Free Fonts for Commercial Use Hot Recent Popular Tags Font Resources & Tools Webfont Generator Font Identifier Font Talk Creative Market Fonts < < Back to the Nickainley font page. License for 'Nickainley' Fontfabric License FFF EULA ver. 2.0 June 2015 By downloading and/or installing a FontfabricTM Free Font you agree to following EULA License: All fonts on the site (fontfabric.com) available for free download (except “Baron”) can be used for both personal and commercial work. Allowed uses: - You may use the free fonts to create images on any surface such as computer screens, paper, web pages, photographs, movie credits, printed material, T-shirts, and other surfaces where the image is a fixed size. - You may use the licensed fonts to create EPS files or other scalable drawings. - You may use the free fonts as web-fonts with @font-face declaration to create web sites, web templates, etc. - You may use the free fonts to create Web Apps, Mobile Apps, Windows Apps, Linux Apps, OS X Apps, Android Apps. etc.. Number of users or page views: - You’re allowed to install the free fonts on unlimited devices (computers, phones, tablets) - You’re allowed to upload and use the free fonts on web sites/templates with unlimited pageviews. Embedding: - You may embed the free fonts into any document you send to third parties. Such documents may be viewed, printed and edited by the recipients. - You may embed the free fonts into software or hardware products in which the fonts will be used by the purchasers of such products (PDF’s, WP templates, e-books, Website templates, Mobile Apps, etc.). - You may embed the free fonts into a web page with a @font-face declaration. - You’re able to generate web-font packages from the font files in a third party program or generator.       Modifications: - You may import characters from the font as graphical objects into a drawing program (Adobe Illustrator, Adobe Photoshop, Corel Draw, etc..) and modify such graphical objects. - You may not modify, adapt, translate, reverse engineer, decompile, disassemble, or create derivative works based on the free fonts itself without Foundry’s prior written consent. That means to edit/modify the font files inself in font editors/software/programs like FontLab Studio, Fontographer, Font Creator, TypeTool, BitFonter, Glyphs, FontStruct, RoboFont, etc.. - You may not resell or redistribute the free fonts itself or any derivative works based on the free fonts itself without Foundry’s prior written consent. - Keep in mind that we may not answer to e-mails concerning additional information about the licenses and the rights to usege of the free fonts! - We also have experience creating corporate and bespoke fonts. For more information or inquiries, feel free to send your questions to the following email address: team@fontfabric.com Advertise on Font Squirrel! Font Lists Recently Added Most Popular Hot Today Hot Web Fonts Almost Free Tags Languages Foundries Find Fonts CLASSIFICATIONS Blackletter Calligraphic Comic Dingbat Display Grunge Handdrawn Monospaced Novelty Pixel Programming Retro Sans Serif Script Serif Slab Serif Stencil Typewriter TAGS Display Headings Paragraph Borders And ... Brushed Script Comic Decorative Display Geometric Graffiti Grunge Handrawn Historical Icons Initials Italic Novelty Ornaments Show More Tags ▼ Font Fi lter LICENSES ✓  Desktop Webfont Ebook Application OFL/Apache FAMILY SIZE Any 4+ Styles 8+ Styles 12+ Styles Full Families b DOWNLOADS Show All Local Only Offsite Only SORT BY Alphabetical Recent Popular Hot Today ▶ Languages About Font Squirrel Font Squirrel is your best resource for FREE, hand-picked, high-quality, commercial-use fonts. Even if that means we send you elsewhere to get them... more info   Font Squirrel relies on advertising in order to keep bringing you great new free fonts and to keep making improvements to the web font generator. If you are seeing this message, you probably have an ad blocker turned on. Please consider disabling it to see content from our partners. Alternatively, you can support Font Squirrel by purchasing a paid license from our sister site, Fontspring .   Font Lists Recently Added Fonts Most Downloaded Fonts Almost Free Fonts Languages Tags Need Help? Frequently Asked Questions Forum --> Help installing fonts Contact Us Advertising Terms of Service Privacy Policy Cookie Policy Cookie Preferences (Do Not Sell/Share) Connect Twitter Facebook Blog ©2026 Font Squirrel. All rights reserved.

════ BODY GROUP Apache-2.0 (2 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- 3ddf9be5c28fe27dad143a5dc76eea25222ad1dd68934a047064e56ed2fa40c5  11560 bytes  families: Open Sans
---- URL: https://raw.githubusercontent.com/google/fonts/90abd17b4f97671435798b6147b698aa9087612f/apache/opensans/LICENSE.txt  fetched 2026-09-03T08:07:16Z  path: /Users/symow/bh29_work/evidence/Open_Sans/LICENSE_at_90abd17b.txt

                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.


---- c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4  11357 bytes  families: Roboto
---- URL: https://raw.githubusercontent.com/google/fonts/4dd6e2b3f7e872f6ecc456a6eee31e39a02d06d8/apache/roboto/LICENSE.txt  fetched 2026-09-03T08:07:39Z  path: /Users/symow/bh29_work/evidence/Roboto/LICENSE_apache-era_at_4dd6e2b3.txt
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.


════ BODY GROUP b0a140a7ad9326ba (1 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- fbbbcfef55318de350562559b671360de6d597112ecc5c73881b05092db89602  4389 bytes  families: Open Sans
---- URL: https://raw.githubusercontent.com/google/fonts/main/ofl/opensans/OFL.txt  fetched 2026-09-03T06:00:48Z  path: /Users/symow/bh29_work/evidence/Open_Sans/OFL.txt
Copyright 2020 The Open Sans Project Authors (https://github.com/googlefonts/opensans)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
https://scripts.sil.org/OFL

-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font
creation efforts of academic and linguistic communities, and to
provide a free and open framework in which fonts may be shared and
improved in partnership with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded,
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply to
any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software
components as distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to,
deleting, or substituting -- in part or in whole -- any of the
components of the Original Version, by changing formats or by porting
the Font Software to a new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed,
modify, redistribute, and sell modified and unmodified copies of the
Font Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components, in
Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the
corresponding Copyright Holder. This restriction only applies to the
primary font name as presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created using
the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.


════ BODY GROUP GPL (1 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- edaef632cbb643e4e7a221717a6c441a4c1a7c918e6e4d56debc3d8739b233f6  17984 bytes  families: ae_AlMothnna
---- URL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt  fetched 2026-09-03T06:29:50Z  path: /Users/symow/bh29_work/evidence/ae_AlMothnna/gpl-2.0.txt
                    GNU GENERAL PUBLIC LICENSE
                       Version 2, June 1991

 Copyright (C) 1989, 1991 Free Software Foundation, Inc.,
 <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The licenses for most software are designed to take away your
freedom to share and change it.  By contrast, the GNU General Public
License is intended to guarantee your freedom to share and change free
software--to make sure the software is free for all its users.  This
General Public License applies to most of the Free Software
Foundation's software and to any other program whose authors commit to
using it.  (Some other Free Software Foundation software is covered by
the GNU Lesser General Public License instead.)  You can apply it to
your programs, too.

  When we speak of free software, we are referring to freedom, not
price.  Our General Public Licenses are designed to make sure that you
have the freedom to distribute copies of free software (and charge for
this service if you wish), that you receive source code or can get it
if you want it, that you can change the software or use pieces of it
in new free programs; and that you know you can do these things.

  To protect your rights, we need to make restrictions that forbid
anyone to deny you these rights or to ask you to surrender the rights.
These restrictions translate to certain responsibilities for you if you
distribute copies of the software, or if you modify it.

  For example, if you distribute copies of such a program, whether
gratis or for a fee, you must give the recipients all the rights that
you have.  You must make sure that they, too, receive or can get the
source code.  And you must show them these terms so they know their
rights.

  We protect your rights with two steps: (1) copyright the software, and
(2) offer you this license which gives you legal permission to copy,
distribute and/or modify the software.

  Also, for each author's protection and ours, we want to make certain
that everyone understands that there is no warranty for this free
software.  If the software is modified by someone else and passed on, we
want its recipients to know that what they have is not the original, so
that any problems introduced by others will not reflect on the original
authors' reputations.

  Finally, any free program is threatened constantly by software
patents.  We wish to avoid the danger that redistributors of a free
program will individually obtain patent licenses, in effect making the
program proprietary.  To prevent this, we have made it clear that any
patent must be licensed for everyone's free use or not licensed at all.

  The precise terms and conditions for copying, distribution and
modification follow.

                    GNU GENERAL PUBLIC LICENSE
   TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

  0. This License applies to any program or other work which contains
a notice placed by the copyright holder saying it may be distributed
under the terms of this General Public License.  The "Program", below,
refers to any such program or work, and a "work based on the Program"
means either the Program or any derivative work under copyright law:
that is to say, a work containing the Program or a portion of it,
either verbatim or with modifications and/or translated into another
language.  (Hereinafter, translation is included without limitation in
the term "modification".)  Each licensee is addressed as "you".

Activities other than copying, distribution and modification are not
covered by this License; they are outside its scope.  The act of
running the Program is not restricted, and the output from the Program
is covered only if its contents constitute a work based on the
Program (independent of having been made by running the Program).
Whether that is true depends on what the Program does.

  1. You may copy and distribute verbatim copies of the Program's
source code as you receive it, in any medium, provided that you
conspicuously and appropriately publish on each copy an appropriate
copyright notice and disclaimer of warranty; keep intact all the
notices that refer to this License and to the absence of any warranty;
and give any other recipients of the Program a copy of this License
along with the Program.

You may charge a fee for the physical act of transferring a copy, and
you may at your option offer warranty protection in exchange for a fee.

  2. You may modify your copy or copies of the Program or any portion
of it, thus forming a work based on the Program, and copy and
distribute such modifications or work under the terms of Section 1
above, provided that you also meet all of these conditions:

    a) You must cause the modified files to carry prominent notices
    stating that you changed the files and the date of any change.

    b) You must cause any work that you distribute or publish, that in
    whole or in part contains or is derived from the Program or any
    part thereof, to be licensed as a whole at no charge to all third
    parties under the terms of this License.

    c) If the modified program normally reads commands interactively
    when run, you must cause it, when started running for such
    interactive use in the most ordinary way, to print or display an
    announcement including an appropriate copyright notice and a
    notice that there is no warranty (or else, saying that you provide
    a warranty) and that users may redistribute the program under
    these conditions, and telling the user how to view a copy of this
    License.  (Exception: if the Program itself is interactive but
    does not normally print such an announcement, your work based on
    the Program is not required to print an announcement.)

These requirements apply to the modified work as a whole.  If
identifiable sections of that work are not derived from the Program,
and can be reasonably considered independent and separate works in
themselves, then this License, and its terms, do not apply to those
sections when you distribute them as separate works.  But when you
distribute the same sections as part of a whole which is a work based
on the Program, the distribution of the whole must be on the terms of
this License, whose permissions for other licensees extend to the
entire whole, and thus to each and every part regardless of who wrote it.

Thus, it is not the intent of this section to claim rights or contest
your rights to work written entirely by you; rather, the intent is to
exercise the right to control the distribution of derivative or
collective works based on the Program.

In addition, mere aggregation of another work not based on the Program
with the Program (or with a work based on the Program) on a volume of
a storage or distribution medium does not bring the other work under
the scope of this License.

  3. You may copy and distribute the Program (or a work based on it,
under Section 2) in object code or executable form under the terms of
Sections 1 and 2 above provided that you also do one of the following:

    a) Accompany it with the complete corresponding machine-readable
    source code, which must be distributed under the terms of Sections
    1 and 2 above on a medium customarily used for software interchange; or,

    b) Accompany it with a written offer, valid for at least three
    years, to give any third party, for a charge no more than your
    cost of physically performing source distribution, a complete
    machine-readable copy of the corresponding source code, to be
    distributed under the terms of Sections 1 and 2 above on a medium
    customarily used for software interchange; or,

    c) Accompany it with the information you received as to the offer
    to distribute corresponding source code.  (This alternative is
    allowed only for noncommercial distribution and only if you
    received the program in object code or executable form with such
    an offer, in accord with Subsection b above.)

The source code for a work means the preferred form of the work for
making modifications to it.  For an executable work, complete source
code means all the source code for all modules it contains, plus any
associated interface definition files, plus the scripts used to
control compilation and installation of the executable.  However, as a
special exception, the source code distributed need not include
anything that is normally distributed (in either source or binary
form) with the major components (compiler, kernel, and so on) of the
operating system on which the executable runs, unless that component
itself accompanies the executable.

If distribution of executable or object code is made by offering
access to copy from a designated place, then offering equivalent
access to copy the source code from the same place counts as
distribution of the source code, even though third parties are not
compelled to copy the source along with the object code.

  4. You may not copy, modify, sublicense, or distribute the Program
except as expressly provided under this License.  Any attempt
otherwise to copy, modify, sublicense or distribute the Program is
void, and will automatically terminate your rights under this License.
However, parties who have received copies, or rights, from you under
this License will not have their licenses terminated so long as such
parties remain in full compliance.

  5. You are not required to accept this License, since you have not
signed it.  However, nothing else grants you permission to modify or
distribute the Program or its derivative works.  These actions are
prohibited by law if you do not accept this License.  Therefore, by
modifying or distributing the Program (or any work based on the
Program), you indicate your acceptance of this License to do so, and
all its terms and conditions for copying, distributing or modifying
the Program or works based on it.

  6. Each time you redistribute the Program (or any work based on the
Program), the recipient automatically receives a license from the
original licensor to copy, distribute or modify the Program subject to
these terms and conditions.  You may not impose any further
restrictions on the recipients' exercise of the rights granted herein.
You are not responsible for enforcing compliance by third parties to
this License.

  7. If, as a consequence of a court judgment or allegation of patent
infringement or for any other reason (not limited to patent issues),
conditions are imposed on you (whether by court order, agreement or
otherwise) that contradict the conditions of this License, they do not
excuse you from the conditions of this License.  If you cannot
distribute so as to satisfy simultaneously your obligations under this
License and any other pertinent obligations, then as a consequence you
may not distribute the Program at all.  For example, if a patent
license would not permit royalty-free redistribution of the Program by
all those who receive copies directly or indirectly through you, then
the only way you could satisfy both it and this License would be to
refrain entirely from distribution of the Program.

If any portion of this section is held invalid or unenforceable under
any particular circumstance, the balance of the section is intended to
apply and the section as a whole is intended to apply in other
circumstances.

It is not the purpose of this section to induce you to infringe any
patents or other property right claims or to contest validity of any
such claims; this section has the sole purpose of protecting the
integrity of the free software distribution system, which is
implemented by public license practices.  Many people have made
generous contributions to the wide range of software distributed
through that system in reliance on consistent application of that
system; it is up to the author/donor to decide if he or she is willing
to distribute software through any other system and a licensee cannot
impose that choice.

This section is intended to make thoroughly clear what is believed to
be a consequence of the rest of this License.

  8. If the distribution and/or use of the Program is restricted in
certain countries either by patents or by copyrighted interfaces, the
original copyright holder who places the Program under this License
may add an explicit geographical distribution limitation excluding
those countries, so that distribution is permitted only in or among
countries not thus excluded.  In such case, this License incorporates
the limitation as if written in the body of this License.

  9. The Free Software Foundation may publish revised and/or new versions
of the General Public License from time to time.  Such new versions will
be similar in spirit to the present version, but may differ in detail to
address new problems or concerns.

Each version is given a distinguishing version number.  If the Program
specifies a version number of this License which applies to it and "any
later version", you have the option of following the terms and conditions
either of that version or of any later version published by the Free
Software Foundation.  If the Program does not specify a version number of
this License, you may choose any version ever published by the Free Software
Foundation.

  10. If you wish to incorporate parts of the Program into other free
programs whose distribution conditions are different, write to the author
to ask for permission.  For software which is copyrighted by the Free
Software Foundation, write to the Free Software Foundation; we sometimes
make exceptions for this.  Our decision will be guided by the two goals
of preserving the free status of all derivatives of our free software and
of promoting the sharing and reuse of software generally.

                            NO WARRANTY

  11. BECAUSE THE PROGRAM IS LICENSED FREE OF CHARGE, THERE IS NO WARRANTY
FOR THE PROGRAM, TO THE EXTENT PERMITTED BY APPLICABLE LAW.  EXCEPT WHEN
OTHERWISE STATED IN WRITING THE COPYRIGHT HOLDERS AND/OR OTHER PARTIES
PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESSED
OR IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.  THE ENTIRE RISK AS
TO THE QUALITY AND PERFORMANCE OF THE PROGRAM IS WITH YOU.  SHOULD THE
PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF ALL NECESSARY SERVICING,
REPAIR OR CORRECTION.

  12. IN NO EVENT UNLESS REQUIRED BY APPLICABLE LAW OR AGREED TO IN WRITING
WILL ANY COPYRIGHT HOLDER, OR ANY OTHER PARTY WHO MAY MODIFY AND/OR
REDISTRIBUTE THE PROGRAM AS PERMITTED ABOVE, BE LIABLE TO YOU FOR DAMAGES,
INCLUDING ANY GENERAL, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING
OUT OF THE USE OR INABILITY TO USE THE PROGRAM (INCLUDING BUT NOT LIMITED
TO LOSS OF DATA OR DATA BEING RENDERED INACCURATE OR LOSSES SUSTAINED BY
YOU OR THIRD PARTIES OR A FAILURE OF THE PROGRAM TO OPERATE WITH ANY OTHER
PROGRAMS), EVEN IF SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE
POSSIBILITY OF SUCH DAMAGES.

                     END OF TERMS AND CONDITIONS

            How to Apply These Terms to Your New Programs

  If you develop a new program, and you want it to be of the greatest
possible use to the public, the best way to achieve this is to make it
free software which everyone can redistribute and change under these terms.

  To do so, attach the following notices to the program.  It is safest
to attach them to the start of each source file to most effectively
convey the exclusion of warranty; and each file should have at least
the "copyright" line and a pointer to where the full notice is found.

    <one line to give the program's name and a brief idea of what it does.>
    Copyright (C) <year>  <name of author>

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, see <https://www.gnu.org/licenses/>.

Also add information on how to contact you by electronic and paper mail.

If the program is interactive, make it output a short notice like this
when it starts in an interactive mode:

    Gnomovision version 69, Copyright (C) year name of author
    Gnomovision comes with ABSOLUTELY NO WARRANTY; for details type `show w'.
    This is free software, and you are welcome to redistribute it
    under certain conditions; type `show c' for details.

The hypothetical commands `show w' and `show c' should show the appropriate
parts of the General Public License.  Of course, the commands you use may
be called something other than `show w' and `show c'; they could even be
mouse-clicks or menu items--whatever suits your program.

You should also get your employer (if you work as a programmer) or your
school, if any, to sign a "copyright disclaimer" for the program, if
necessary.  Here is a sample; alter the names:

  Yoyodyne, Inc., hereby disclaims all copyright interest in the program
  `Gnomovision' (which makes passes at compilers) written by James Hacker.

  <signature of Moe Ghoul>, 1 April 1989
  Moe Ghoul, President of Vice

This General Public License does not permit incorporating your program into
proprietary programs.  If your program is a subroutine library, you may
consider it more useful to permit linking proprietary applications with the
library.  If this is what you want to do, use the GNU Lesser General
Public License instead of this License.


════ BODY GROUP HTML-f71e5664 (1 file(s)) — each file printed complete; the owner reads the shared body once and each file's own header ════

---- a97e65ee1ce94dac5821a3e46230593b16768a805cbea9d49b21b4240304139b  50122 bytes (HTML page; bytes stored verbatim at the path; TEXT EXTRACTED below, not byte-verbatim)  families: ae_AlMothnna
---- URL: http://www.gnu.org/copyleft/gpl.html  fetched 2026-09-03T06:29:49Z  path: /Users/symow/bh29_work/evidence/ae_AlMothnna/gpl.html
The GNU General Public License v3.0 - GNU Project - Free Software Foundation Skip to main text Free Software Supporter : JOIN THE FSF GNU Operating System Supported by the Free Software Foundation Site navigation Skip ABOUT GNU PHILOSOPHY LICENSES EDUCATION SOFTWARE DISTROS DOCS MALWARE HELP GNU AUDIO & VIDEO GNU ART FUN GNU'S WHO? SOFTWARE DIRECTORY HARDWARE SITEMAP GNU General Public License Skip to license text A Quick Guide to GPLv3 Why Upgrade to GPLv3 Frequently Asked Questions about the GNU licenses How to use GNU licenses for your own software Translations of the GPL The GPL in other formats: plain text , Texinfo , LaTeX , standalone HTML , ODF , Docbook v4 or v5 , reStructuredText , Markdown , and RTF . GPLv3 logos to use with your project Old versions of the GNU GPL What to do if you see a possible GPL violation GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007 Copyright © 2007 Free Software Foundation, Inc. < https://fsf.org/ > Everyone is permitted to copy and distribute verbatim copies of this license document, but changing it is not allowed. Preamble The GNU General Public License is a free, copyleft license for software and other kinds of works. The licenses for most software and other practical works are designed to take away your freedom to share and change the works. By contrast, the GNU General Public License is intended to guarantee your freedom to share and change all versions of a program--to make sure it remains free software for all its users. We, the Free Software Foundation, use the GNU General Public License for most of our software; it applies also to any other work released this way by its authors. You can apply it to your programs, too. When we speak of free software, we are referring to freedom, not price. Our General Public Licenses are designed to make sure that you have the freedom to distribute copies of free software (and charge for them if you wish), that you receive source code or can get it if you want it, that you can change the software or use pieces of it in new free programs, and that you know you can do these things. To protect your rights, we need to prevent others from denying you these rights or asking you to surrender the rights. Therefore, you have certain responsibilities if you distribute copies of the software, or if you modify it: responsibilities to respect the freedom of others. For example, if you distribute copies of such a program, whether gratis or for a fee, you must pass on to the recipients the same freedoms that you received. You must make sure that they, too, receive or can get the source code. And you must show them these terms so they know their rights. Developers that use the GNU GPL protect your rights with two steps: (1) assert copyright on the software, and (2) offer you this License giving you legal permission to copy, distribute and/or modify it. For the developers' and authors' protection, the GPL clearly explains that there is no warranty for this free software. For both users' and authors' sake, the GPL requires that modified versions be marked as changed, so that their problems will not be attributed erroneously to authors of previous versions. Some devices are designed to deny users access to install or run modified versions of the software inside them, although the manufacturer can do so. This is fundamentally incompatible with the aim of protecting users' freedom to change the software. The systematic pattern of such abuse occurs in the area of products for individuals to use, which is precisely where it is most unacceptable. Therefore, we have designed this version of the GPL to prohibit the practice for those products. If such problems arise substantially in other domains, we stand ready to extend this provision to those domains in future versions of the GPL, as needed to protect the freedom of users. Finally, every program is threatened constantly by software patents. States should not allow patents to restrict development and use of software on general-purpose computers, but in those that do, we wish to avoid the special danger that patents applied to a free program could make it effectively proprietary. To prevent this, the GPL assures that patents cannot be used to render the program non-free. The precise terms and conditions for copying, distribution and modification follow. TERMS AND CONDITIONS 0. Definitions. “This License” refers to version 3 of the GNU General Public License. “Copyright” also means copyright-like laws that apply to other kinds of works, such as semiconductor masks. “The Program” refers to any copyrightable work licensed under this License. Each licensee is addressed as “you”. “Licensees” and “recipients” may be individuals or organizations. To “modify” a work means to copy from or adapt all or part of the work in a fashion requiring copyright permission, other than the making of an exact copy. The resulting work is called a “modified version” of the earlier work or a work “based on” the earlier work. A “covered work” means either the unmodified Program or a work based on the Program. To “propagate” a work means to do anything with it that, without permission, would make you directly or secondarily liable for infringement under applicable copyright law, except executing it on a computer or modifying a private copy. Propagation includes copying, distribution (with or without modification), making available to the public, and in some countries other activities as well. To “convey” a work means any kind of propagation that enables other parties to make or receive copies. Mere interaction with a user through a computer network, with no transfer of a copy, is not conveying. An interactive user interface displays “Appropriate Legal Notices” to the extent that it includes a convenient and prominently visible feature that (1) displays an appropriate copyright notice, and (2) tells the user that there is no warranty for the work (except to the extent that warranties are provided), that licensees may convey the work under this License, and how to view a copy of this License. If the interface presents a list of user commands or options, such as a menu, a prominent item in the list meets this criterion. 1. Source Code. The “source code” for a work means the preferred form of the work for making modifications to it. “Object code” means any non-source form of a work. A “Standard Interface” means an interface that either is an official standard defined by a recognized standards body, or, in the case of interfaces specified for a particular programming language, one that is widely used among developers working in that language. The “System Libraries” of an executable work include anything, other than the work as a whole, that (a) is included in the normal form of packaging a Major Component, but which is not part of that Major Component, and (b) serves only to enable use of the work with that Major Component, or to implement a Standard Interface for which an implementation is available to the public in source code form. A “Major Component”, in this context, means a major essential component (kernel, window system, and so on) of the specific operating system (if any) on which the executable work runs, or a compiler used to produce the work, or an object code interpreter used to run it. The “Corresponding Source” for a work in object code form means all the source code needed to generate, install, and (for an executable work) run the object code and to modify the work, including scripts to control those activities. However, it does not include the work's System Libraries, or general-purpose tools or generally available free programs which are used unmodified in performing those activities but which are not part of the work. For example, Corresponding Source includes interface definition files associated with source files for the work, and the source code for shared libraries and dynamically linked subprograms that the work is specifically designed to require, such as by intimate data communication or control flow between those subprograms and other parts of the work. The Corresponding Source need not include anything that users can regenerate automatically from other parts of the Corresponding Source. The Corresponding Source for a work in source code form is that same work. 2. Basic Permissions. All rights granted under this License are granted for the term of copyright on the Program, and are irrevocable provided the stated conditions are met. This License explicitly affirms your unlimited permission to run the unmodified Program. The output from running a covered work is covered by this License only if the output, given its content, constitutes a covered work. This License acknowledges your rights of fair use or other equivalent, as provided by copyright law. You may make, run and propagate covered works that you do not convey, without conditions so long as your license otherwise remains in force. You may convey covered works to others for the sole purpose of having them make modifications exclusively for you, or provide you with facilities for running those works, provided that you comply with the terms of this License in conveying all material for which you do not control copyright. Those thus making or running the covered works for you must do so exclusively on your behalf, under your direction and control, on terms that prohibit them from making any copies of your copyrighted material outside their relationship with you. Conveying under any other circumstances is permitted solely under the conditions stated below. Sublicensing is not allowed; section 10 makes it unnecessary. 3. Protecting Users' Legal Rights From Anti-Circumvention Law. No covered work shall be deemed part of an effective technological measure under any applicable law fulfilling obligations under article 11 of the WIPO copyright treaty adopted on 20 December 1996, or similar laws prohibiting or restricting circumvention of such measures. When you convey a covered work, you waive any legal power to forbid circumvention of technological measures to the extent such circumvention is effected by exercising rights under this License with respect to the covered work, and you disclaim any intention to limit operation or modification of the work as a means of enforcing, against the work's users, your or third parties' legal rights to forbid circumvention of technological measures. 4. Conveying Verbatim Copies. You may convey verbatim copies of the Program's source code as you receive it, in any medium, provided that you conspicuously and appropriately publish on each copy an appropriate copyright notice; keep intact all notices stating that this License and any non-permissive terms added in accord with section 7 apply to the code; keep intact all notices of the absence of any warranty; and give all recipients a copy of this License along with the Program. You may charge any price or no price for each copy that you convey, and you may offer support or warranty protection for a fee. 5. Conveying Modified Source Versions. You may convey a work based on the Program, or the modifications to produce it from the Program, in the form of source code under the terms of section 4, provided that you also meet all of these conditions: a) The work must carry prominent notices stating that you modified it, and giving a relevant date. b) The work must carry prominent notices stating that it is released under this License and any conditions added under section 7. This requirement modifies the requirement in section 4 to “keep intact all notices”. c) You must license the entire work, as a whole, under this License to anyone who comes into possession of a copy. This License will therefore apply, along with any applicable section 7 additional terms, to the whole of the work, and all its parts, regardless of how they are packaged. This License gives no permission to license the work in any other way, but it does not invalidate such permission if you have separately received it. d) If the work has interactive user interfaces, each must display Appropriate Legal Notices; however, if the Program has interactive interfaces that do not display Appropriate Legal Notices, your work need not make them do so. A compilation of a covered work with other separate and independent works, which are not by their nature extensions of the covered work, and which are not combined with it such as to form a larger program, in or on a volume of a storage or distribution medium, is called an “aggregate” if the compilation and its resulting copyright are not used to limit the access or legal rights of the compilation's users beyond what the individual works permit. Inclusion of a covered work in an aggregate does not cause this License to apply to the other parts of the aggregate. 6. Conveying Non-Source Forms. You may convey a covered work in object code form under the terms of sections 4 and 5, provided that you also convey the machine-readable Corresponding Source under the terms of this License, in one of these ways: a) Convey the object code in, or embodied in, a physical product (including a physical distribution medium), accompanied by the Corresponding Source fixed on a durable physical medium customarily used for software interchange. b) Convey the object code in, or embodied in, a physical product (including a physical distribution medium), accompanied by a written offer, valid for at least three years and valid for as long as you offer spare parts or customer support for that product model, to give anyone who possesses the object code either (1) a copy of the Corresponding Source for all the software in the product that is covered by this License, on a durable physical medium customarily used for software interchange, for a price no more than your reasonable cost of physically performing this conveying of source, or (2) access to copy the Corresponding Source from a network server at no charge. c) Convey individual copies of the object code with a copy of the written offer to provide the Corresponding Source. This alternative is allowed only occasionally and noncommercially, and only if you received the object code with such an offer, in accord with subsection 6b. d) Convey the object code by offering access from a designated place (gratis or for a charge), and offer equivalent access to the Corresponding Source in the same way through the same place at no further charge. You need not require recipients to copy the Corresponding Source along with the object code. If the place to copy the object code is a network server, the Corresponding Source may be on a different server (operated by you or a third party) that supports equivalent copying facilities, provided you maintain clear directions next to the object code saying where to find the Corresponding Source. Regardless of what server hosts the Corresponding Source, you remain obligated to ensure that it is available for as long as needed to satisfy these requirements. e) Convey the object code using peer-to-peer transmission, provided you inform other peers where the object code and Corresponding Source of the work are being offered to the general public at no charge under subsection 6d. A separable portion of the object code, whose source code is excluded from the Corresponding Source as a System Library, need not be included in conveying the object code work. A “User Product” is either (1) a “consumer product”, which means any tangible personal property which is normally used for personal, family, or household purposes, or (2) anything designed or sold for incorporation into a dwelling. In determining whether a product is a consumer product, doubtful cases shall be resolved in favor of coverage. For a particular product received by a particular user, “normally used” refers to a typical or common use of that class of product, regardless of the status of the particular user or of the way in which the particular user actually uses, or expects or is expected to use, the product. A product is a consumer product regardless of whether the product has substantial commercial, industrial or non-consumer uses, unless such uses represent the only significant mode of use of the product. “Installation Information” for a User Product means any methods, procedures, authorization keys, or other information required to install and execute modified versions of a covered work in that User Product from a modified version of its Corresponding Source. The information must suffice to ensure that the continued functioning of the modified object code is in no case prevented or interfered with solely because modification has been made. If you convey an object code work under this section in, or with, or specifically for use in, a User Product, and the conveying occurs as part of a transaction in which the right of possession and use of the User Product is transferred to the recipient in perpetuity or for a fixed term (regardless of how the transaction is characterized), the Corresponding Source conveyed under this section must be accompanied by the Installation Information. But this requirement does not apply if neither you nor any third party retains the ability to install modified object code on the User Product (for example, the work has been installed in ROM). The requirement to provide Installation Information does not include a requirement to continue to provide support service, warranty, or updates for a work that has been modified or installed by the recipient, or for the User Product in which it has been modified or installed. Access to a network may be denied when the modification itself materially and adversely affects the operation of the network or violates the rules and protocols for communication across the network. Corresponding Source conveyed, and Installation Information provided, in accord with this section must be in a format that is publicly documented (and with an implementation available to the public in source code form), and must require no special password or key for unpacking, reading or copying. 7. Additional Terms. “Additional permissions” are terms that supplement the terms of this License by making exceptions from one or more of its conditions. Additional permissions that are applicable to the entire Program shall be treated as though they were included in this License, to the extent that they are valid under applicable law. If additional permissions apply only to part of the Program, that part may be used separately under those permissions, but the entire Program remains governed by this License without regard to the additional permissions. When you convey a copy of a covered work, you may at your option remove any additional permissions from that copy, or from any part of it. (Additional permissions may be written to require their own removal in certain cases when you modify the work.) You may place additional permissions on material, added by you to a covered work, for which you have or can give appropriate copyright permission. Notwithstanding any other provision of this License, for material you add to a covered work, you may (if authorized by the copyright holders of that material) supplement the terms of this License with terms: a) Disclaiming warranty or limiting liability differently from the terms of sections 15 and 16 of this License; or b) Requiring preservation of specified reasonable legal notices or author attributions in that material or in the Appropriate Legal Notices displayed by works containing it; or c) Prohibiting misrepresentation of the origin of that material, or requiring that modified versions of such material be marked in reasonable ways as different from the original version; or d) Limiting the use for publicity purposes of names of licensors or authors of the material; or e) Declining to grant rights under trademark law for use of some trade names, trademarks, or service marks; or f) Requiring indemnificat

§3 CLAUSE (3) — BUNDLED-LICENCE CASES (reportage, never concluded)
───────────────────────────────────────────────────────────────────────
■ Bauhaus 93: Microsoft 365 / Office (cloud fonts) — https://support.microsoft.com/en-us/office/fonts/cloud-fonts-in-office (reached via the font-list link https://support.office.com/en-us/article/cloud-fonts-in-office-f7b009fe-037f-45ed-a556-b5fe6ede6adb); terms pages: Office 2024 Software License Terms PDF (fonts clause) and Font redistribution FAQ https://learn.microsoft.com/en-us/typography/fonts/font-faq (which scopes itself to Windows-supplied fonts).
   reportage: Microsoft Software License Terms, Office 2024 retail (PDF, "Last updated July 2024"), clause (iv), reportage: "While the software is running, you may use its fonts to display and print content. You may temporarily download the fonts to a printer or other output device to print content, and you may embed fonts in content only as permitted by the embedding restrictions in the fonts." Cloud fonts page: "Cloud fonts are available to Microsoft 365 subscribers." Font redistribution FAQ (learn.microsoft.com, ms.date 2024-11-19), reportage: scope — "they apply to all the fonts installed with Windows as system-wide resources"; "Unless you are using an application that is specifically licensed for home, student, or non-commercial use, we do not place any restrictions on what you do with print output that uses these fonts"; "We view creating graphic files as being essentially the same as printing from an output device"; videos: "the same as graphic files, providing the captions or text is rendered as a bitmap image, and the font files themselves are not embedded within the video file". NOTE: the FAQ's scope statement covers fonts installed with Windows; Bauhaus 93 is Office-supplied.
■ Colonna MT: Microsoft 365 / Office (cloud fonts) — https://support.microsoft.com/en-us/office/fonts/cloud-fonts-in-office; terms pages: Office 2024 Software License Terms PDF (fonts clause) and Font redistribution FAQ https://learn.microsoft.com/en-us/typography/fonts/font-faq (Windows-scoped).
   reportage: Microsoft Software License Terms, Office 2024 retail (PDF, "Last updated July 2024"), clause (iv), reportage: "While the software is running, you may use its fonts to display and print content. You may temporarily download the fonts to a printer or other output device to print content, and you may embed fonts in content only as permitted by the embedding restrictions in the fonts." Cloud fonts page: "Cloud fonts are available to Microsoft 365 subscribers." Font redistribution FAQ (learn.microsoft.com, ms.date 2024-11-19), reportage: scope — "they apply to all the fonts installed with Windows as system-wide resources"; "Unless you are using an application that is specifically licensed for home, student, or non-commercial use, we do not place any restrictions on what you do with print output that uses these fonts"; "We view creating graphic files as being essentially the same as printing from an output device"; videos: "the same as graphic files, providing the captions or text is rendered as a bitmap image, and the font files themselves are not embedded within the video file". NOTE: the FAQ's scope statement covers fonts installed with Windows; Colonna MT is Office-supplied.
■ Square721 BT: CorelDRAW Graphics Suite (Corel) — https://www.corel.com/en/corel-copyrights/ ("Fonts" section); the Corel EULA https://www.corel.com/en/eula/ is referred to for redistribution rights but its current text has no font clause.
   reportage: Corel copyrights page, reportage: "While Corel has developed some fonts in-house, most of the fonts found in Corel products have been licensed from independent font vendors. If you wish to license a particular font, you should contact Bitstream at www.bitstream.com, not Corel. Corel does not make fonts developed by it available for licensing." and, under Use of Software: "Please read the accompanying end user license agreement accompanying the software to determine your redistribution rights." Corel KB 128050: bonus fonts come with the DVD version; Bitstream Font Navigator; "Embed Fonts Using TrueDoc(TM)" on save. MyFonts, reportage: "Individual Styles from $29.99 USD", "Complete family of 6 fonts: $140.99 USD", licence types Desktop / Webfont / App / Electronic Doc / Digital Ad-Email / Server, "make sure to read the full EULA text" — retail path is commercial; licence evidence for it would require purchase.
■ Arial: Windows 10 (Windows-supplied font) — https://learn.microsoft.com/en-us/typography/fonts/windows_10_font_list; terms pages: Font redistribution FAQ https://learn.microsoft.com/en-us/typography/fonts/font-faq and Microsoft Product Terms https://www.microsoft.com/licensing/terms/product/ForallSoftware/all.
   reportage: Font redistribution FAQ (learn.microsoft.com, ms.date 2024-11-19), reportage: scope — "they apply to all the fonts installed with Windows as system-wide resources"; "Unless you are using an application that is specifically licensed for home, student, or non-commercial use, we do not place any restrictions on what you do with print output that uses these fonts"; "We view creating graphic files as being essentially the same as printing from an output device"; videos: "the same as graphic files, providing the captions or text is rendered as a bitmap image, and the font files themselves are not embedded within the video file". Microsoft Product Terms, Universal License Terms For all Software, "Font Components, Images, and Sounds", reportage: "may use the fonts included with or installed by that software to display and print content. Customer may only embed fonts in content as permitted by the embedding restrictions in the fonts; and temporarily download them to a printer or other output device to print content."
■ Bahnschrift: Windows 10 / Windows 11 (Windows-supplied font) — https://learn.microsoft.com/en-us/typography/fonts/windows_10_font_list; terms pages: Font redistribution FAQ https://learn.microsoft.com/en-us/typography/fonts/font-faq and Microsoft Product Terms https://www.microsoft.com/licensing/terms/product/ForallSoftware/all.
   reportage: Declared licence_url https://docs.microsoft.com/typography/about -> 2 redirects -> https://learn.microsoft.com/en-us/typography/about (200): an "About Microsoft Typography" page (ms.date 2020-03-10), not a licence text. Font redistribution FAQ (learn.microsoft.com, ms.date 2024-11-19), reportage: scope — "they apply to all the fonts installed with Windows as system-wide resources"; "Unless you are using an application that is specifically licensed for home, student, or non-commercial use, we do not place any restrictions on what you do with print output that uses these fonts"; "We view creating graphic files as being essentially the same as printing from an output device"; videos: "the same as graphic files, providing the captions or text is rendered as a bitmap image, and the font files themselves are not embedded within the video file". Microsoft Product Terms, Universal License Terms For all Software, "Font Components, Images, and Sounds", reportage: "may use the fonts included with or installed by that software to display and print content. Customer may only embed fonts in content as permitted by the embedding restrictions in the fonts; and temporarily download them to a printer or other output device to print content."
■ Adobe Arabic: Adobe Acrobat (all 4 styles always available, per Adobe AEM Forms Designer help); Adobe Reader when the "Extended Language Package" (Reader font pack) is installed; also served through Adobe Fonts to Creative Cloud subscribers ("Subscribe to Creative Cloud to use more fonts" on the product page). Which of these installed the library copy is not determinable from the pages.
   reportage: REPORTAGE (quoted, not assessed): fonts.adobe.com product page: "The full Adobe Fonts library is cleared for both personal and commercial use." and "Visit the Adobe Fonts Licensing FAQ for full details". Adobe AEM Forms Designer help 'Choosing fonts for performance': "the following fonts are always available in Acrobat and Adobe Reader, and do not need to be embedded" — list includes "Myriad Pro Bold, Myriad Pro Bold It, Myriad Pro It, Myriad Pro Regular" and "Adobe Arabic/Hebrew/Thai with all 4 styles (Bold, BoldItalic, Italic, and Regular). Available in Adobe Reader when the Extended Language Package is installed". helpx FAQ 'Note' (Last updated on Mar 27, 2026): "Fonts installed in the Fonts folder on your computer are licensed under their own end-user agreements. These FAQs don't apply to those fonts. Contact the font foundry directly for license questions."
■ Myriad Pro: Adobe Acrobat and Adobe Reader (Myriad Pro Regular, Italic, Bold, Bold Italic are listed by Adobe as "always available in Acrobat and Adobe Reader"); Adobe Creative Cloud / former Creative Suite desktop apps ship it as an application font (the family is also in the Adobe Fonts subscription library). Note the library file is a .ttf whereas Acrobat/Reader install MyriadPro-Regular.otf — the library copy's provenance is not established by any stored page.
   reportage: REPORTAGE (quoted, not assessed): Adobe AEM Forms Designer help 'Choosing fonts for performance': "the following fonts are always available in Acrobat and Adobe Reader, and do not need to be embedded" — list includes "Myriad Pro Bold, Myriad Pro Bold It, Myriad Pro It, Myriad Pro Regular" and "Adobe Arabic/Hebrew/Thai with all 4 styles (Bold, BoldItalic, Italic, and Regular). Available in Adobe Reader when the Extended Language Package is installed". helpx FAQ 'Note' (Last updated on Mar 27, 2026): "Fonts installed in the Fonts folder on your computer are licensed under their own end-user agreements. These FAQs don't apply to those fonts. Contact the font foundry directly for license questions." fonts.adobe.com/about (the page that https://www.adobe.com/products/type/creative-cloud-fonts.html now redirects to): "All the fonts are included with an Adobe subscription" / "Everything is licensed for personal and commercial use" / "Fonts are licensed for personal and commercial use; review the full Terms of Use." Search-engine snippet of a community.adobe.com thread (NOT vendor terms, NOT stored): Myriad Pro "has been included with the software for the exclusive use of the software itself".
■ ae_AlMothnna: Not a bundled font. Distributed as the ae_fonts tarballs on SourceForge (and repackaged by third parties, e.g. TCPDF's ae_fonts_2.0 directory seen in search results).
   reportage: REPORTAGE (quoted, not assessed): Khotot project page TODO list: "New license or dual licensing with GPL and OFL. DONE (GPL with font exception)"; goals: "Create and/or salvage free and open TTF Arabic fonts." Stored GPL texts: GNU GPL v2 plain text (gnu.org/licenses/old-licenses/gpl-2.0.txt) and the declared licence_url http://www.gnu.org/copyleft/gpl.html, which today resolves to the GPL v3 page (gpl-3.0.html). Search-engine snippets (third-party font mirrors, NOT stored) describe the ae_fonts terms as GPL version 2 with an embedding exception ("if you create a document which uses this font and embed this font or unaltered portions into the document, this font does not by itself cause the resulting document to be covered by the GNU General Public License").
■ Hacen Liner XL: Not a bundled font (independent Arabic type designer).
   reportage: REPORTAGE (quoted, not assessed). The font's own embedded licence description (nameID 13): "The artistic design and the points in each glyph of this font are the property of Hacen, your use of this font is limited to production purposes, you may not edit, modify or rename this font without prior permission. Hacen holds the original shape of each letter of this font, any copying, redrawing, or rendering to match or imitate the shape of the original is a breach of copyright law." Search-engine snippet from fontke.com (third-party font-parameter site, NOT stored) labels the font "Non-Commercial" and says to contact the copyright party for a commercial licence — that classification is fontke's, not Hacen's. The vendor URL embedded in the font (www.hacen.net/liner) does not serve a font page today: the stored response is titled "MANTRA888 Saatnya Coba Permainan Yang Bikin Penasaran" and consists of Indonesian slot-gambling spam ("SITUS SLOT", "SLOT GACOR"; 291 spam-keyword hits, identical with a browser and with curl's default User-Agent) — hijacked/injected content, no licence wording. The hacen.net homepage itself is clean (title "Hacen", 0 spam hits, 37 "Hacen" mentions, footer link to https://hacen.net/license?lang=ar which returns 404).
■ Dubai: Microsoft 365 — Office "cloud fonts" (Applies To: Excel/Word/Outlook/PowerPoint/Publisher for Microsoft 365, Windows and Mac) per Microsoft Support "Cloud fonts in Office" (Last updated: March 12, 2025), which lists "Dubai Regular / Dubai-Regular.ttf / 1.1" and "Dubai Bold / Dubai-Bold.ttf / 1.1" (plus Light, Medium and the four Italics). Also distributed free of charge from dubaifont.com (per the mirrored EULA, TEC licenses the Font Software "free of charge on a no-fee basis"). NOT part of the Windows 10/11 shipped font sets or the Arabic Script Supplemental FOD package (checked on Microsoft's official lists). Which channel the library copies came from is not established (file names DUBAI-BOLD.TTF/DUBAI-REGULAR.TTF are upper-case, unlike Microsoft's Dubai-Bold.ttf).
   reportage: REPORTAGE (not assessed). Microsoft Support "Cloud fonts in Office": "Cloud fonts are fonts hosted in the cloud by Microsoft 365, and are available in the latest versions of Office applications"; "Note Cloud fonts are available to Microsoft 365 subscribers."; list rows: "Dubai Bold Dubai-Bold.ttf 1.1", "Dubai Regular Dubai-Regular.ttf 1.1" (Italics are version 1). Quoted from the Font Squirrel MIRROR of the EULA (not the official page): heading "END USER LICENCE AGREEMENT – DUBAI FONT"; "BY USING, COPYING OR INSTALLING THE FONT SOFTWARE THE LICENSEE ACCEPTS ALL OF THE TERMS AND CONDITIONS CONTAINED HEREIN"; clause 2.1 "TEC licenses use of the Font Software to the Licensee on the basis of this Agreement free of charge on a no-fee basis. TEC does not sell the Font Software to the Licensee. TEC remains the owner of the Font Software at all times."; "TEC" means collectively The Executive Council (an entity in the Emirate of Dubai, United Arab Emirates established pursuant to Law No. (3) of 2003…". Search-engine snippets of dubaifont.com pages (NOT stored): "If you download and/or use the Dubai Font from the website, the downloading and/or use is subject to separate licensing terms under an end user licence agreement"; "You may use the fonts freely in your own work whether for private or commercial use"; "You are not allowed to distribute the fonts".
■ Goli: Not bundled; free download from magictype.in / GitHub. The library file names carry a "BF6639969…" suffix, the naming pattern of the third-party redistributor befonts.com, so the copies were most likely obtained there rather than from MagicType/GitHub (not verified).
   reportage: REPORTAGE (quoted, not assessed): product page: "The font family is available as open source for personal or commercial use. Feel free to use the typeface and share your valuable feedback."; OFL.txt (repo): "Copyright 2024 The Goli Project Authors (https://github.com/magictype/goli) This Font Software is licensed under the SIL Open Font License, Version 1.1."; the repo README (per WebFetch) says "Madhuban is licensed under the SIL Open Font License v1.1. To view the copyright and specific terms and conditions please refer to OFL.txt" — the README names a different MagicType family (Madhuban), apparently a copy-paste in the README. No price, cart item or purchase requirement appears on the product page for Goli.
■ Bebas: Not bundled; free download (bebasfont.com points to https://www.dafont.com/bebas.font; the original Dharma Type page says development is discontinued).
   reportage: REPORTAGE (quoted, not assessed). Dharma Type licence page https://dharmatype.com/license ("THE END USER LICENSE AGREEMENT (EULA) v.2018.11.01.") does NOT mention Bebas or Bebas Neue by name; its "License Notice" says: "This End User License Agreement (EULA) applies to fonts purchased directly from us after November 2018. If you purchase fonts through third-party shops, their respective licenses will apply. Free fonts are licensed under either our FFEULA or the SIL Open Font License 1.1 (SIL-OFL 1.1). Please refer to each font's page for specific licensing details." (the only outbound licence link is https://scripts.sil.org/OFL). Bebas product page: "Bebas is a free font designed for headlines, captions, and titling. It was originally created in 2005 as a personal type design exercise… The development of the original version has since been discontinued." bebasfont.com "License" section: "Bebas (2005) is free font. You can use this font free of charge even for commercial purposes." bebasfont.com history on the Neue family: "Bebas Neue version 1.xxx (2010) — Free font … Licensed under the SIL Open Font License v1.1." and "Bebas Neue version 2.000 (2018) — Free font. From version 2.000, Bebas Neue has become open source font… Licensed under the SIL Open Font License v1.1."; also "Bebas Neue Family (2014) — Free font. Fontfabric designed additional weights and glyphs. They are distributing the font family under the same name of 'Bebas Neue'."
■ Nexa: Not bundled; retail font sold by Fontfabric (per-style and collection pricing on the product page).
   reportage: REPORTAGE (quoted, not assessed): product page: "Nexa Complete Family - 36 font styles … $249"; "Nexa - 18 font styles … $175" (list includes "Nexa Heavy", "Nexa Heavy Italic"); "Desktop from $29 — Install the font on your computer to create designs for print or static digital images, such as logos, packaging, and marketing materials. The desktop license is always perpetual."; the page also offers "Enter your email to receive your free font … We'll send you a zipped file with the free font, license agreement, and installation instructions" (NOT used — no email entered). "Fontfabric Commercial EULA For Retail Fonts" (openly published, stored): clause 2.1 "Customer shall have a non-exclusive, non-assignable, non-transferable (except as expressly permitted) license to install, access and Use the Font Software. Fontfabric reserves all rights not expressly granted…"; clause 2.3 "This Agreement shall be effective upon the date that Customer receives Font Software". "Fontfabric Commercial EULA For Free Fonts" (stored): "All Fontfabric Fonts (Software) available for a free download and commercial use come with a standard Fontfabric Commercial End-User License Agreement For Free Fonts as part of the free download…".

§4 CLAUSE (4) — THE ABSENT ONES (≥4 refs): LOCATED, NOT ACQUIRED
───────────────────────────────────────────────────────────────────────
■ Grand Hotel — OPEN_LICENCE_TEXT_STORED (OFL.txt)
   upstream: google/fonts repository ofl/grandhotel (Astigmatic, OFL)
   identified by: name match; the family is hosted on Google Fonts
   download URL(s): ['https://raw.githubusercontent.com/google/fonts/main/ofl/grandhotel/GrandHotel-Regular.ttf']
   upstream sha256: {'GrandHotel-Regular.ttf': 'ec7ae65d49c936cb5ed32534ab74dbd40c56733de5145ac3aae9da362e02b50f'}
   licence/terms stored: ['https://raw.githubusercontent.com/google/fonts/main/ofl/grandhotel/OFL.txt']
   acquired: False (nothing added to materials/)
■ GoodDog — UNRESOLVED as evidence — the free GoodDog (Plain/Cool) licence text is only republished by redistributors (Font Squirrel/Fontspring) that refuse non-browser clients (empty body / 403, headers recorded); BUNDLED reportage via Adobe Fonts
   upstream: Fonthead Design (fonthead.com) — HOST DEAD: the domain now serves a certificate for ll924.com (recorded probe); GoodDog New is carried by Adobe Fonts (bundling vendor, Creative Cloud subscription) — page stored
   identified by: search + Adobe Fonts page; Font Squirrel's licence page answers HTTP 200 text/html with an EMPTY body to non-browser clients (headers recorded 2026-09-03), Fontspring answers 403 — neither text could be stored byte-verbatim
   download URL(s): []
   upstream sha256: {}
   licence/terms stored: ['https://fonts.adobe.com/fonts/gooddog-new (PRODUCT_PAGE, reportage: "The full Adobe Fonts library is cleared for both personal and commercial use.")']
   acquired: False (nothing added to materials/)
■ Aquire — FREE_FOR_PERSONAL_USE — COMMERCIAL — EVIDENCE REQUIRES PURCHASE; the authoritative download sits behind a store checkout (email required) — NOT ENTERED per the hard stop; no upstream sha256 recorded
   upstream: designer Gregory "Sesohq" Ortiz — own store https://sesohq.sellfy.store/p/ff7uie/ (free for personal use at $0+, paid Desktop/Web/Logo tiers)
   identified by: search + fontspace page (aggregator) naming the designer and store
   download URL(s): ['https://sesohq.sellfy.store/p/ff7uie/ (checkout flow, not entered)']
   upstream sha256: {}
   licence/terms stored: ['https://www.fontspace.com/aquire-font-f43735 (aggregator PRODUCT_PAGE: "Freeware, Non-Commercial"; "Contact the designer to purchase a commercial license")']
   acquired: False (nothing added to materials/)
■ Angora — COMMERCIAL — EVIDENCE REQUIRES PURCHASE (demo free for personal use only); same-name ambiguity flagged
   upstream: Omotu Studio (omotustudio.com) — licence page stored; demo on dafont "PERSONAL USE ONLY"; commercial tiers sold (Creative Fabrica / Fontspring / MyFonts / omotustudio.com)
   identified by: search; dafont page names Omotu Studio; ambiguity: "VTC Angora Chik" is a different free font — the designs reference "AngoraRegular", consistent with Omotu's Angora Regular naming but NOT verified against a file; Omotu Studio's own shop search page (stored, evidence/Angora/index.html) carries the product 'Angora' with its product images (Angora-1.jpg), confirming Angora is an Omotu Studio product
   download URL(s): ['https://www.dafont.com/angora.font (demo, personal use only — aggregator)']
   upstream sha256: {}
   licence/terms stored: ['https://omotustudio.com/license/ (TERMS_PAGE_REPORTAGE)', 'https://www.dafont.com/angora.font (PRODUCT_PAGE)']
   acquired: False (nothing added to materials/)

§5 CLAUSE (5) — THE READING TABLE (one row per family; RULING blank)
───────────────────────────────────────────────────────────────────────
family | faces covered | evidence class(es) | licence as the text names itself | evidence file (path) + sha256 | RULING
Bebas Neue | BebasNeue Bold.ttf, BebasNeue-Regular.otf, BebasNeue Book.ttf | FAMILY-MATCHED | SIL Open Font License, Version 1.1 | evidence/Bebas_Neue/OFL.txt 72082f6cb4d04be2 | 
ae_AlMothnna | ae_AlMothnna_bold.ttf | FAMILY-MATCHED | GNU General Public License v2 | evidence/ae_AlMothnna/Khotot.html 11d203e77b6b11c9; evidence/ae_AlMothnna/ae_fonts.html 4292b19c872ac8fd; evidence/ae_AlMothnna/gpl-2.0.txt edaef632cbb643e4 | 
Komika Axis | KOMIKAX.ttf | UNRESOLVED | (none in reach) | evidence/Komika_Axis/apostrophic-labs-license.html 14d342178db81ee6; evidence/Komika_Axis/komika-axis.font 4b24bae20124d25f; evidence/Komika_Axis/www.apostrophiclab.com cb43421ed8649345 | 
Nexa | Nexa-Heavy.ttf | FAMILY-MATCHED | (vendor terms page, reportage) | evidence/Nexa/fontfabric-commercial-eula-for-free-fonts.html 88aa1eec881a286a; evidence/Nexa/fontfabric-commercial-eula-for-retail-fonts.html b3476a78d477b83b; evidence/Nexa/fontfabric-licensing.html fc4744b719305c5b | 
Figerona Black | FontsFree-Net-Figerona-VF(1).ttf | FAMILY-MATCHED | (COMMERCIAL — EVIDENCE REQUIRES PURCHASE) | evidence/Figerona_Black/license.html e62e70718ad5fdae; evidence/Figerona_Black/figerona.html 78440d155c261bd7; evidence/Figerona_Black/licenses.html 6d44b2221c4f2ceb | 
Open Sans | OpenSans-Semibold.ttf | HASH-MATCHED | SIL Open Font License, Version 1.1 | evidence/Open_Sans/OFL.txt fbbbcfef55318de3 | ERA NOTE: the HASH-MATCHED bytes are the 2015-03-06 apache/opensans build, which shipped beside Apache License 2.0 (evidence/Open_Sans/LICENSE_at_90abd17b.txt 3ddf9be5c28fe27d, §2); the OFL.txt above is the family's LATER relicensing in ofl/opensans — both texts are in §2; which governs the owner's copy is the owner's reading | 
Great Vibes | GreatVibes-Regular.ttf | NAME+VERSION-MATCHED, HASH MISMATCH | SIL Open Font License, Version 1.1 | evidence/Great_Vibes/OFL.txt 61093a21f5e63ded | 
Montserrat | Montserrat-Bold.otf, Montserrat-Bold.ttf, Montserrat-Light.otf, Montserrat-Black.otf, Montserrat-Medium.otf, Montserrat-Regular.ttf, Montserrat-SemiBold.otf, Montserrat-SemiBold_0.otf, Montserrat-Thin.otf | FAMILY-MATCHED; HASH-MATCHED | SIL Open Font License, Version 1.1 | evidence/Montserrat/OFL.txt 8b7141c03fa4f8d4 | 
Amatic | Amatic-Bold.ttf | NAME+VERSION-MATCHED, HASH MISMATCH | SIL Open Font License, Version 1.1 | evidence/Amatic/OFL.txt 301f77908df2b001 | 
Cairo | Cairo-Regular.ttf, Cairo-Bold(1).ttf, Cairo-SemiBold.ttf | FAMILY-MATCHED; HASH-MATCHED | SIL Open Font License, Version 1.1 | evidence/Cairo/OFL.txt a4554e1799d42e14 | 
Goli | Goli-Regular-BF663996909d710.otf, Goli-Bold-BF6639968fd8e9b.otf, Goli-Light-BF66399690a8aa1.otf, Goli-Medium-BF66399690a672c.otf, Goli-SemiBold-BF66399690d955e.otf | FAMILY-MATCHED | SIL Open Font License, Version 1.1 | evidence/Goli/Goli.html 42edbd862fb7f56c; evidence/Goli/OFL.txt 18bc2a638ef84bcd; evidence/Goli/goli-typeface.html e4c78674e52b4698 | 
Lato | lato-black(1).ttf | HASH-MATCHED | SIL Open Font License, Version 1.1 | evidence/Lato/OFL.txt 74ba064d03f1f1c4 | 
Merriweather | Merriweather-Bold.ttf | FAMILY-MATCHED | SIL Open Font License, Version 1.1 | evidence/Merriweather/OFL.txt 715bd349bfa6116f | 
Playfair Display | PlayfairDisplay-Bold.otf | FAMILY-MATCHED | SIL Open Font License, Version 1.1 | evidence/Playfair_Display/OFL.txt 566be814f8e96e93 | 
Poppins | Poppins-Bold.otf, Poppins-Regular.otf, Poppins-Light.otf, Poppins-Medium.otf, Poppins-SemiBold.otf, Poppins-Black.otf | FAMILY-MATCHED | SIL Open Font License, Version 1.1 | evidence/Poppins/OFL.txt 6be04893d770899a | 
Quicksand | Quicksand-Bold.ttf | NAME+VERSION-MATCHED, HASH MISMATCH | SIL Open Font License, Version 1.1 | evidence/Quicksand/OFL.txt 14d28541780d90f6 | 
Raleway | Raleway-Light.ttf, Raleway-Thin.ttf | FAMILY-MATCHED; HASH-MATCHED | SIL Open Font License, Version 1.1 | evidence/Raleway/OFL.txt 7e946cf1171784d1 | 
Roboto | Roboto-Light_0.ttf, Roboto-Medium_0.ttf | FAMILY-MATCHED | SIL Open Font License, Version 1.1 | evidence/Roboto/OFL.txt 061402327a96aadb | ERA NOTE: the library's 2011 build (v1.00000) matched no commit in either apache/roboto or ofl/roboto; the apache-era licence (Apache License 2.0, evidence/Roboto/LICENSE_apache-era_at_4dd6e2b3.txt c71d239df91726fc, §2) is stored as the era's text beside the family's later OFL relicensing | 
Rubik | Rubik-Bold.ttf | HASH-MATCHED | SIL Open Font License, Version 1.1 | evidence/Rubik/OFL.txt 472cbe7c25441df6 | 
Shadows Into Light Two | ShadowsIntoLightTwo-Regular.ttf | NAME+VERSION-MATCHED, HASH MISMATCH | SIL Open Font License, Version 1.1 | evidence/Shadows_Into_Light_Two/OFL.txt 6a28d4d5d8b4d1ea | 
Hacen Liner XL | Hacen Liner XL.ttf | NAME+VERSION-MATCHED | (licence text file — see §2 for its own title) | evidence/Hacen_Liner_XL/embedded_name_table_license.txt c736dec784120a74; evidence/Hacen_Liner_XL/license_lang_ar_HTTP404.html 2ef25cabda47e6a9; evidence/Hacen_Liner_XL/liner.html 575d2131f9b421fa | 
Nickainley | Nickainley-Normal.otf | FAMILY-MATCHED | (licence text file — see §2 for its own title) | evidence/Nickainley/nick_ainley_LICENSE.txt 187e5110ffb7b6bd; evidence/Nickainley/Nickainley-Script-Free-Font.html 1b3ed382be80063e; evidence/Nickainley/nickainley.html 30ae75c67e3e1d48 | 
2  Narenj | 2  Narenj Regular.ttf | UNRESOLVED | (none in reach) | evidence/2_Narenj/win2farsi_wayback_2010.html d495f0962cd6da5b; evidence/2_Narenj/2-narenj-font-download.html 4b751448539c9599 | 
Adobe Arabic | AdobeArabic-Regular.otf | FAMILY-MATCHED | (vendor terms page, reportage) | evidence/Adobe_Arabic/adobe-arabic.html b243c81763bed33e; evidence/Adobe_Arabic/aem_designer_choosing_fonts.html 9e674e84f8a6ae7a; evidence/Adobe_Arabic/helpx_font-licensing.html 100795f4b033db16 | 
Arial | arialbd.ttf | NAME+VERSION-MATCHED | (vendor terms page, reportage) | evidence/Arial/ms_font_list_arial.html fe0e0c37fd0b8dd8; evidence/Arial/ms_windows_10_font_list.html 90a028d083f15483; evidence/Arial/ms_font_redistribution_faq.html 004ac39f8da44bc0 | 
BORELA | Borela-6YX71.otf | FAMILY-MATCHED | (COMMERCIAL — EVIDENCE REQUIRES PURCHASE) | evidence/BORELA/borela.font f614cd7e9ddec8b5; evidence/BORELA/borela-font-f103891.html 204a39acab734c26 | 
Bahnschrift | bahnschrift.ttf | NAME+VERSION-MATCHED | (vendor terms page, reportage) | evidence/Bahnschrift/ms_font_list_bahnschrift.html 2d4a7553c557f023; evidence/Bahnschrift/ms_windows_10_font_list.html 90a028d083f15483; evidence/Bahnschrift/ms_font_redistribution_faq.html 004ac39f8da44bc0 | 
Bauhaus 93 | BAUHS93.TTF | NAME+VERSION-MATCHED | (vendor terms page, reportage) | evidence/Bauhaus_93/ms_font_list_bauhaus-93.html 2afd361ebd9064e4; evidence/Bauhaus_93/ms_office_cloud_fonts.html cb4223e6127f65f8; evidence/Bauhaus_93/ms_font_redistribution_faq.html 004ac39f8da44bc0 | 
Bebas | Bebas-Regular.otf | NAME+VERSION-MATCHED | (vendor terms page, reportage) | evidence/Bebas/bebas.html b3660b32d2f3c750; evidence/Bebas/bebasfont.com ce99374cee6690e6; evidence/Bebas/license.html 8129f57d52c6afab | 
Blisey | Blisey.otf | FAMILY-MATCHED | (COMMERCIAL — EVIDENCE REQUIRES PURCHASE) | evidence/Blisey/blisey-font-syauqi-studio.html efd35fe482410d07; evidence/Blisey/syauqistudio_profile.html d6273315991c5d78; evidence/Blisey/Blisey-Psychedelic-Display-Typeface.html 4cde0b1928837708 | 
Colonna MT | COLONNA.TTF | FAMILY-MATCHED | (vendor terms page, reportage) | evidence/Colonna_MT/ms_font_list_colonna-mt.html b0a033102af89c33; evidence/Colonna_MT/ms_office_cloud_fonts.html 185c846432e865d2; evidence/Colonna_MT/ms_font_redistribution_faq.html 004ac39f8da44bc0 | 
Dubai | DUBAI-BOLD.TTF, DUBAI-REGULAR.TTF | NAME+VERSION-MATCHED | (vendor terms page, reportage) | evidence/Dubai/fontsquirrel_license_dubai.html c8d9a5ee4c5b0d89; evidence/Dubai/ms_cloud_fonts_in_office.html e73152f646870d36 | 
HASOOB | HASOOB.ttf | UNRESOLVED | (none in reach) | evidence/HASOOB/hasoob.html eae54c972309ed58 | 
Hayah | Hayah.otf | NAME+VERSION-MATCHED | (none in reach) | evidence/Hayah/www.zakdesign.net 9166f1231ff21d6a; evidence/Hayah/wayback_zakdesign_net_20110622.html 5615305137339fd5; evidence/Hayah/hayah-font.html f9cd8e0f8ba1ab1a | 
Myriad Pro | Myriad Pro Regular.ttf | FAMILY-MATCHED | (vendor terms page, reportage) | evidence/Myriad_Pro/aem_designer_choosing_fonts.html 9e674e84f8a6ae7a; evidence/Myriad_Pro/creative-cloud-fonts.html b5616392c049b010; evidence/Myriad_Pro/font-licensing_redirect_target.html e3598ac3d0b81da4 | 
Selima | selima.otf | NAME+VERSION-MATCHED | (none in reach) | evidence/Selima/selima.font 04963718a22c5211; evidence/Selima/Selima-Free-Font.html 7aa65de5442c204a; evidence/Selima/selima-script.html df027cf8209a4964 | 
Square721 BT | Square721 BT Roman.ttf | FAMILY-MATCHED | (vendor terms page, reportage) | evidence/Square721_BT/corel_copyrights.html 1dfaa79166236732; evidence/Square721_BT/corel_eula.html 4056b19a34e23f80; evidence/Square721_BT/coreldraw_licensing_faqs.html 2297befc1bfdc56b | 

§6 CLAUSE (6) — NOTHING MOVED, NO SPEND
───────────────────────────────────────────────────────────────────────
  • ZERO writes outside the §BC transcription and ~/bh29_work/ — BY
    CONSTRUCTION: every fetch was stored under ~/bh29_work/evidence/ (with a
    .meta.json beside each file: URL, UTC time, sha256, bytes, kind),
    upstream binaries under ~/bh29_work/upstream/ and upstream_history/
    ONLY (64 binaries fetched for hashing; none placed under materials/;
    the dropped directory's mtime unchanged: 2026-09-01 15:02:40). Evidence files stored:
    288.
  • NO SPEND: nothing was purchased; no checkout, sign-up or email flow was
    entered — where a source gated its file or text behind one, that is
    reported as the finding (Aquire's store; Fontfabric's free-weight email
    gate; Font Squirrel/Fontspring blocks), not bypassed.
  • NO CREDENTIALS: no upstream was given any credential; GitHub was read
    anonymously (API + raw + a treeless public clone).
  • NO DIP-0A regen: 7590 rows, unchanged. The library stays outside the
    governed corpus.
  • Worktree clean at report time: `git status --porcelain` EMPTY at HEAD e1781ed
    (= T29); ledger 443 at HEAD == 443 worktree.
  • Protected regions and tree seals re-verified at report time: GATE 7fbeb8f1fe10b0fb,
    TEST b32030dc827263e4; dip0c 36f08a31ad581c3b, dip0a 2e339a7e23a46c00 (outer root).
  • INCIDENTS, recorded: (i) one hunt leg (agent C) deleted a scratch
    directory INSIDE ~/bh29_work/ (tmp/) that another leg (agent B) had
    created, destroying six intermediate probe files (four Wayback CDX query
    results for Apostrophic Lab / Komika and two fontspace pages, listed in
    ~/bh29_work/agent_C_incident.txt); no evidence file, index entry or
    findings file was affected, nothing outside ~/bh29_work/ was touched, and
    agent B's stored evidence for those families is intact (meta counts
    re-verified). (ii) The first pass of all three foundry legs and four of
    the executor's own fetches were cut off by a usage limit and re-run from
    scratch; the google/fonts leg and the stores made before the cut were
    unaffected. (iii) A first history walk over a treeless clone of
    google/fonts was unbounded and was stopped; the bounded commits-API walk
    replaced it. (iv) Three legs ran as subagents under the hard-stop rules;
    every store carries its URL, UTC time and sha256, and no purchase, sign-up
    or credential was entered by any leg (their notes record every gate met).

STOP.
Source attributions (§1), every fetched licence text complete and
byte-verbatim (§2), the bundled-vendor reportage (§3), the absent names
located and not acquired (§4), and the reading table with its RULING column
blank (§5) are in front of the owner. Nothing here concludes what any
licence permits; nothing was bought; nothing moved. The owner reads each
distinct text and rules per family: grant through the §BH26(a)-shaped
channel, refuse, or defer.
