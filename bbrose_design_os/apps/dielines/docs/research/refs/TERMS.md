# TERMS: where each reference file came from and the terms it was taken under

All files were obtained on **2026-10-07** (local time; PDF CreationDate stamps read 2026-10-06 ~18:1x UTC). I drove each site's own public generator page in a headless Chromium (Playwright): I opened the page, typed the dimensions, clicked the site's own download buttons, and saved what the site handed over. No account was created and nothing was logged into or paid for. No API key was used, and no robots rule, paywall or bot checkpoint was bypassed. I did not take any site's code out to run elsewhere.

The files are **unmodified** as downloaded, including each site's own metadata/credit line. Each `*_settings.png` is a screenshot of the generator's parameter panel at the moment of download. It shows which inputs produced which file.

Intended use (as briefed): a private comparison of geometry against our own generated carton, and a side-by-side picture shown to the owner. Nothing here is resold or redistributed.

---

## 1. Box Blanks (boxblanks.com): PRIMARY reference

- Generator pages used:
  - STE: `https://boxblanks.com/#/ecma-a1001-straight-tuck` (style page `https://boxblanks.com/styles/ste/`)
  - RTE: `https://boxblanks.com/#/ecma-a1050-reverse-tuck` (style page `https://boxblanks.com/styles/rte/`)
- Terms page: `https://boxblanks.com/terms/` ("Last updated 2026-09-03")
- robots.txt: `User-agent: *` / `Allow: /`
- Account needed: none. Terms §1: "It is free, needs no account, and everything is generated in your browser."

Quoted terms (verbatim):

> "Short version: the files are yours to use, including commercially. They come with no guarantee of accuracy and no liability of any kind — cut and fold a sample before you spend money on tooling. Do not scrape the site or resell it as your own service."

> "2. The files you download — Dielines you generate here, on this site, are yours to use for any purpose, including commercial work. You may modify them, share them, send them to a converter, and use them in products you sell. No attribution is required and no licence fee is payable. Exported files carry a line of metadata naming where they came from. You are free to remove it."

> "8. What you may not do — Systematically scrape, harvest or bulk-download the catalogue by automated means · Copy the site's code and run it as your own service · Present Box Blanks output as your own generator, or resell access to it · Use the site in a way that degrades it for others. Generating the dielines you actually need — however many that is — is exactly what the site is for and is not restricted."

> "3. ... we do not warrant that any dieline is accurate. A generated blank may contain errors. It may not match the FEFCO or ECMA construction whose code it displays. ... Where a template is marked as having been checked against the published plate, that records that a visual comparison was carried out. It is not a guarantee that the file is correct, and it is not a certification of conformity with any standard."

> Page footer: "© 2026 Box Blanks. Dielines generated on this site are yours to use, commercially or otherwise, with no attribution required. Files obtained through the API are licensed under the API terms."

How the files were obtained: six dielines (2 styles × 3 dimension modes) were generated one at a time through the site's own UI. That is "generating the dielines you actually need", not catalogue scraping. The HTTP API was **not** used: it needs a key issued by email and has separate terms (`https://boxblanks.com/api-terms/`).

Inputs for every Box Blanks file: Length 22, Width 22, Height 105. Board "Cartonboard 350 gsm (0.45 mm)" (the default), Caliper 0.45, Glue lap width 12 (the default), Display window none, Euro hang slot off. Advanced settings left at their defaults: Tuck tongue length 0 = auto, Relief cut 0 = board thickness, 3 mm bleed guide off. The only thing changed between files is **Measured as**: `Inside dimensions` / `Crease to crease` / `Outside dimensions`.

## 2. Die Cut Studio (diecutstudio.com): SECONDARY cross-check

- Generator pages used:
  - STE: `https://www.diecutstudio.com/templates/straight-tuck-end`, then the page's own link "Open the Straight Tuck End in the editor →" (`/editor?model=tuck-end`)
  - RTE: `https://www.diecutstudio.com/templates/reverse-tuck-end`, then its own editor link (`/editor?model=reverse-tuck-end`)
- Terms: no separate terms page exists (`/terms`, `/legal`, `/license`, `/privacy` all return 404 on 2026-10-07). The usage statement is printed in each template page's FAQ.
- robots.txt: `User-agent: *` / `Allow: /` (it also explicitly welcomes ClaudeBot / anthropic-ai).
- Account needed: none.

Quoted terms (verbatim, from the template pages):

> STE page: "Is the Straight Tuck End template free? Yes. The Straight Tuck End dieline generates free in your browser — no signup and no watermark — and is yours to use for personal and commercial projects."

> RTE page: "Is the Reverse Tuck End template free? Yes. The Reverse Tuck End dieline generates free in your browser — no signup and no watermark — and is yours to use for personal and commercial projects." · "Price: Free — no account, no watermark"

Inputs for every Die Cut Studio file:
- Units mm. Length (L) 22, Width/depth (W) 22, Height (H) 105, Material thickness 0.45.
- Bleed 3.18 (the default 0.125 in). No window, no hanger slot.
- STE: Top notch and Bottom notch ON (the defaults).
- RTE: "Thumb cut (easy-open, front lip)" OFF (the default).
- Changed between files: **Outer** / **Inner**.

---

## 3. File list with SHA-256 (as downloaded, unmodified)

| File | SHA-256 | Bytes |
|---|---|---|
| boxblanks_RTE_22x22x105_crease_t0.45.dxf | 298696ad9a242384f3e11205a36c253e0893a037c111c784418dfafb7aa61d27 | 6180 |
| boxblanks_RTE_22x22x105_crease_t0.45.pdf | 7c6b4569a442f099ba6869b88570a2496adb11113a5fdfdb321c8ed89eef8e0c | 2312 |
| boxblanks_RTE_22x22x105_crease_t0.45.svg | c7f6860a5bc9f97f5a49cdb457a6aa1c51c9858f9155af661d35c43031496783 | 1763 |
| boxblanks_RTE_22x22x105_inside_t0.45.dxf | 6cc9067a83c556e131b6905a7d892fadac1d3a9853cef34fc8264d83736b62a6 | 6921 |
| boxblanks_RTE_22x22x105_inside_t0.45.pdf | d851b91cb0c7043739524d30ec6b32ffb1509aa09fc4e1346cb194aeeebe51e3 | 2320 |
| boxblanks_RTE_22x22x105_inside_t0.45.svg | 67b2672f26a5f5a417c4fca99cce15b0c1573a712bce85d6817c3d5794d88291 | 1995 |
| boxblanks_RTE_22x22x105_outside_t0.45.dxf | 898312a776995097196974c0c5b0aa7bf7d374a924b14fe1164bf82cd3b116fb | 6965 |
| boxblanks_RTE_22x22x105_outside_t0.45.pdf | ea87a3d305199f4bdd5cb934152c3bb1f8d0237e54d2ada53deb8e3d2271c72f | 2336 |
| boxblanks_RTE_22x22x105_outside_t0.45.svg | ca29589f5a79bf9d4b16f267a219dea219b8e05c35ae1b2cfc462d2a6dc8f881 | 1991 |
| boxblanks_STE_22x22x105_crease_t0.45.dxf | caf4e6ace9035b5f96eaaac8c5c3363848c3abb0a324a93da6e61106fa9af7be | 6216 |
| boxblanks_STE_22x22x105_crease_t0.45.pdf | 793aa6d4897ab1815028b1876b3fcfbf2ac0a530f2c97098d55558cbb5ce622f | 2264 |
| boxblanks_STE_22x22x105_crease_t0.45.svg | 4c281f4db26b7529a5f2cc00f7ff0d00514c1dcda3292678156d0c1b47ada008 | 1763 |
| boxblanks_STE_22x22x105_inside_t0.45.dxf | 49645670dee6c9e98f4b929ac23ad4735de00f0298a0ad35890008bf76757178 | 6795 |
| boxblanks_STE_22x22x105_inside_t0.45.pdf | 548d8582261a9c2f05a82b4d2e450cae94ee624098e7986b685cc884366831a1 | 2270 |
| boxblanks_STE_22x22x105_inside_t0.45.svg | 72fcb7e2d8b02eb6e099f62431ce9b6cdeda3b81f23b44caa370e7bbc2e241f5 | 1994 |
| boxblanks_STE_22x22x105_outside_t0.45.dxf | c2d5c765f68376affb38378427a45832420bd934ba3e5075abe1323139c27d0d | 6690 |
| boxblanks_STE_22x22x105_outside_t0.45.pdf | c490dc46c68154576f0fcd058bace463e82be384a0abc4e62f17021c17b12340 | 2289 |
| boxblanks_STE_22x22x105_outside_t0.45.svg | caf7b3db4910b67a891a24754e69b544422583f5f1ff9e54450d7c6d0098b7fd | 1990 |
| diecutstudio_RTE_22x22x105_inner_t0.45.dxf | a3234ada7c0b7141937d6331d872f31af1ad81999acb73651c7137c82f21cce1 | 6876 |
| diecutstudio_RTE_22x22x105_inner_t0.45.pdf | 15f4e2900096027caf65abc0995bc7b611d9b27ee71a1c1ccd8dbb7e939da89f | 1692 |
| diecutstudio_RTE_22x22x105_inner_t0.45.svg | e1751f39f3d74a81c80f3cf2654059f3b1ade05b140d8e2278c249ca0d30193a | 4189 |
| diecutstudio_RTE_22x22x105_outer_t0.45.dxf | ad6af2025c343e43295c2bf728c7b1a042acb97f17e6eb42dec4ec0bcb440c97 | 6902 |
| diecutstudio_RTE_22x22x105_outer_t0.45.pdf | e19167f8b4f4eeecac38b325b58219c02371f826aa1111b679fc7f99b7d9498c | 1667 |
| diecutstudio_RTE_22x22x105_outer_t0.45.svg | 65ae886ce74e16ede6c48a810dcc87e8e61c0c226cea2ccafe66076ac84c20e2 | 4166 |
| diecutstudio_STE_22x22x105_inner_t0.45.dxf | 24fe38689f1ee14313a1587bb3d22ceba30a50e8f16890ee6d084d5f098fad44 | 6390 |
| diecutstudio_STE_22x22x105_inner_t0.45.pdf | db292b2cabc34b8ae7090a2fd6218aaf8267a6c7f723552f7817ca4cecd209d7 | 1824 |
| diecutstudio_STE_22x22x105_inner_t0.45.svg | 8fcc710e8d52d93258f70adf3f394fc7521e304790758886031d0b0a07cac1ac | 4461 |
| diecutstudio_STE_22x22x105_outer_t0.45.dxf | 90e393d79fff9bfdf3a13cbbf106809b8b7a82fde52a64d499704c329a0f4779 | 6283 |
| diecutstudio_STE_22x22x105_outer_t0.45.pdf | 708383c1a6885b551d2f14fb64055fbd8ebd9d786aed51aeaffbc81abf513e31 | 1816 |
| diecutstudio_STE_22x22x105_outer_t0.45.svg | 5bedf9060411ebbc9eb61e5895ae9cb2ea031f7e1e06b35b4cc5508dbaf027d6 | 4421 |

The screenshots (`*_settings.png`, and `*_export_panel.png` for Die Cut Studio) are my own captures of the public pages at download time. They are proof of inputs and are not themselves dielines.

---

## 4. Sources looked at but NOT downloaded

Their terms are quoted in REFERENCES.md §1:

- Pacdora
- diecuttemplates.com
- Boxshot dielines
- cefBox
- Newprint
- templatemaker.nl
- PackagingTools.io
- Custom Packly
- BD Print
- BrandMyDispo
- packmyman.com
- DDR68/Rhino_Packaging_Toolkit. It is MIT-licensed and is the source of our own formulas, so it is not an independent reference.
- PakFactory
- Packhelp
