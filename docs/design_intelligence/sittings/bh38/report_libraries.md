### 3a. Colours the libraries offer, by source pack and tier

Extraction is by STRUCTURE only (the §BH35 rule — never guessed from pixels): Illustrator/Photoshop **XMP swatch groups** (`xmpTPg:SwatchGroups`, named document swatches, CMYK/RGB/GRAY converted to hex without an ICC profile — an approximation), the one **.ase** swatch file (RGB, exact), **SVG declared colours** (exact), **PDF separations** and XMP **spot swatches** (PANTONE names — no hex invented), and **DSC custom colours** in EPS prologs (CMYK, approximated). Tier = the row of the tier record at HEAD.

**PRODUCTION (embeddable) — 1 colour-bearing pack** (of the 16 PRODUCTION rows, only the layered .ai carries structural colour; the rasters carry pixels, which the rule does not read):

| Pack | Files with swatches | Process swatches (hex, CMYK→sRGB approx.) | Spot swatches (names) |
|---|---|---|---|
| ALL..MOCKUP/27-4-2024/delicious-summer-fruits | 2 | `#231F20`×4, `#ED1C24`×4, `#FFFFFF`×2, `#FFF200`×2, `#00A651`×2, `#00AEEF`×2, `#2E3192`×2, `#EC008C`×2, `#BE1E2D`×2, `#EF4136`×2, `#F15A29`×2, `#F7941E`×2, `#FBB040`×2, `#F9ED32`×2, `#D7DF23`×2, `#8DC63F`×2 | PANTONE 1345 C, PANTONE 7411 C, PANTONE 7412 C, PANTONE 178 C, PANTONE Warm Red C, PANTONE 7527 C, PANTONE 3025 C, PANTONE 3035 C, PANTONE 303 C, PANTONE 179 C, PANTONE 180 C, PANTONE 181 C |

**REFERENCE (inspiration only) — 410 colour-bearing packs**: 406 with XMP swatch groups, 42 with spot swatches, 31 with PDF separations, 1 with SVG colours, 1 with an .ase file, 6 with DSC custom colours. Illustrator's default swatch set (White, Black, CMYK Red …) dominates the XMP counts; the packs' OWN swatches are the spot names and the non-default process colours. Top packs by structural colour count:

| Pack | Files w/ swatches | Distinct process hex | Spot names (top) | Separations (top) | Other |
|---|---|---|---|---|---|
| 17-10-2024 | 28 | 60 | PANTONE 7408 C, PANTONE 2612 C, PANTONE 189 C, PANTONE 7653 C, PANTONE 1345 C | Black, Magenta, Yellow, Cyan, PANTONE 1345 C | .ase: `#FAB4BF`, `#FFD2C7`, `#FFF1DD`, `#FFE2E8`, `#F8FFB5` |
| 17-10-2024/Telegram Desktop | 19 | 60 | PANTONE 494 C, PANTONE 9243 C, PANTONE 9243 U, PANTONE 7432 C, PANTONE 305 C | PANTONE 494 C, Black, PANTONE 9243 C, Yellow, Magenta |  |
| ALL..MOCKUP/27-4-2024 | 5 | 56 | PANTONE 293 C, PANTONE Reflex Blue C, PANTONE 1585 C, PANTONE 802 C | PANTONE 293 C, PANTONE Reflex Blue C, PANTONE 1585 C, PANTONE 802 C | SVG: `#000000`, `#E8E8E8`, `#030303`, `#F1F1F1`, `#E5E5E5`, `#010101` |
| 17-10-2024/abstract-boho-contemporary-cover-collection | 1 | 60 | ANPA 754-0 AdPro, ANPA 703-0 AdPro, ANPA 703-6 AdPro, ANPA 703-8 AdPro, ANPA 757-0 AdPro |  | DSC: `#FF9172` ANPA 756-8 AdPro |
| 17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون | 20 | 60 | PANTONE Orange 021 C, PANTONE 318 C, PANTONE 134 C, PANTONE Yellow 0131 C, PANTONE 494 C | PANTONE 134 C, Black, Magenta, Yellow, PANTONE 494 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face wac | 1 | 55 | PANTONE Orange 021 C, PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C, PANTONE 1345 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day crea | 1 | 55 | PANTONE 189 C, PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C, PANTONE 1345 C | Black, Cyan, Magenta, PANTONE 1345 C, PANTONE 1665 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/LIP PALM | 1 | 56 | PANTONE 7408 C, PANTONE 7653 C, PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day crea | 1 | 55 | PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C, PANTONE 1345 C, PANTONE 7408 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/hair oil | 1 | 55 | PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C, PANTONE 1345 C, PANTONE 7408 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/SUN SCRE | 1 | 55 | PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C, PANTONE 1345 C, PANTONE 7408 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/FACE OIL | 1 | 55 | PANTONE 2612 C, PANTONE 1345 C, PANTONE 486 C, PANTONE 189 C, PANTONE 635 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face ser | 1 | 55 | PANTONE 189 C, PANTONE 486 C, PANTONE 7408 C, PANTONE 7653 C, PANTONE 2612 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/NIGHT DA | 1 | 55 | PANTONE 7408 C, PANTONE 7653 C, PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |

Across REFERENCE: **145 distinct spot swatch names** (top: PANTONE 1665 C ×25, PANTONE 7408 C ×24, PANTONE 2612 C ×24, PANTONE 189 C ×24, PANTONE 7653 C ×24, PANTONE 1345 C ×24, PANTONE 486 C ×24, PANTONE 635 C ×24); **53 distinct separation colorants** (top: Yellow ×52, Magenta ×51, Black ×50, PANTONE 1345 C ×24, PANTONE 1665 C ×24, PANTONE 189 C ×24); **1926 distinct process hexes** — the whole list is in `~/bh38_work/libraries.json`. The one .ase file (`17-10-2024/AdobeColor Spring Peach.ase`, REFERENCE) carries `#FAB4BF #FFD2C7 #FFF1DD #FFE2E8 #F8FFB5`.

### 3b. Materials the libraries offer, by tier

**PRODUCTION (16 rows — the assets the channel raised; each carries its pack's evidence and, for the Freepik packs, the credit condition):**

| File | Kind | Canvas / page | Colour mode, depth, dpi | Layers / smart objects / replaceable-by-name | Profile |
|---|---|---|---|---|---|
| 17-10-2024/pile-online-shopping-package-mockups/65757.psd | PSD (layered mockup) | 5000×3337 px | RGB, 16-bit, 300 dpi | 2 / 1 / — | — |
| ALL..MOCKUP/27-4-2024/logo-mockup-luxury-box/130.psd | PSD (layered mockup) | 3600×2400 px | RGB, 8-bit, 300 dpi | 8 / 1 / REPLACE THIS SCREEN | — |
| ALL..MOCKUP/27-4-2024/green-packaging-cosmetic-products(2)/2512866.psd | PSD (layered mockup) | 4800×3000 px | RGB, 8-bit, 300 dpi | 18 / 2 / Place your design here (Double click to , Place your design here (Double click to  | — |
| ALL..MOCKUP/27-4-2024/delicious-summer-fruits/116297-OPHTKC-8.ai | AI (PDF-compatible) | 176.39×176.39 mm | — | images on page 0: 0; separations: none | — |
| ALL..MOCKUP/27-4-2024/fonts bold/coolvetica/Typodermic Desktop EULA 2023.pdf | PDF vector | 215.9×279.4 mm | — | fonts: ArialMT, Calibri, Calibri-Bold; separations: none | — |
| ALL..MOCKUP/27-4-2024/delicious-summer-fruits/116297-OPHTK5-790.eps | EPS vector | (EPS: no page box read) | — | fonts: —; separations: none | — |
| ALL..MOCKUP/عبوات مواد تجميل/makeup-realistic-items-super-set-with-mascara-powder-isolated-vector-illustration/16260.eps | EPS vector | (EPS: no page box read) | — | fonts: —; separations: none | — |
| ALL..MOCKUP/عبوات مواد تجميل/nail-polish/7077.eps | EPS vector | (EPS: no page box read) | — | fonts: —; separations: none | — |
| ALL..MOCKUP/عبوات مواد تجميل/cosmetics-package-realistic-transparent-set/18207.eps | EPS vector | (EPS: no page box read) | — | fonts: —; separations: none | — |
| 17-10-2024/pile-online-shopping-package-mockups/65757.jpg | JPEG raster | 5000×3337 px | RGB, dpi 300 | — | Adobe RGB (1998) |
| ALL..MOCKUP/27-4-2024/logo-mockup-luxury-box/130.jpg | JPEG raster | 3600×2400 px | RGB, dpi 300 | — | Adobe RGB (1998) |
| ALL..MOCKUP/27-4-2024/green-packaging-cosmetic-products(2)/2512865.jpg | JPEG raster | 4800×3000 px | RGB, dpi 300 | — | sRGB IEC61966-2.1 |
| ALL..MOCKUP/27-4-2024/delicious-summer-fruits/116297-OPHTK7-614.jpg | JPEG raster | 2000×2000 px | RGB, dpi — | — | sRGB IEC61966-2.1 |
| ALL..MOCKUP/عبوات مواد تجميل/makeup-realistic-items-super-set-with-mascara-powder-isolated-vector-illustration/16260.jpg | JPEG raster | 4500×4500 px | RGB, dpi 100 | — | none |
| ALL..MOCKUP/عبوات مواد تجميل/nail-polish/7077.jpg | JPEG raster | 4500×4500 px | RGB, dpi 100 | — | none |
| ALL..MOCKUP/عبوات مواد تجميل/cosmetics-package-realistic-transparent-set/18207.jpg | JPEG raster | 4500×4500 px | RGB, dpi 720 | — | none |

**REFERENCE (inspiration only):**

- **Layered PSD: 454 files** — 380 with ≥1 smart object, 391 with a replaceable-by-name layer ("Place your design here", "REPLACE THIS SCREEN" …); modes RGB 403, GRAYSCALE 50, CMYK 1; depth 8-bit 439, 16-bit 15; dpi 300 ×250, 72 ×123, 48 ×50, 240 ×20; canvases (top) 256×256 ×50, 4000×3000 ×39, 5376×3584 ×21, 3584×5376 ×18, 3333×5000 ×9; 309 at ≥ 12 Mpx; median 14 layers.
- **Layered AI (PDF-compatible): 362 files** — 100 carry separations (spot plates), 116 carry a placed image on page 0; page sizes (top) 176×176 mm ×92, 265×176 mm ×32, 210×297 mm ×30, 307×220 mm ×26.
- **Vectors: 1408 files** — .ai 680, .eps 656, .svg 53, .pdf 17; 8 with separations.
- **Rasters: 2079 files** — modes RGB 1949, RGBA 101, P 28, CMYK 1; 1351 with a long side ≥ 3000 px; 856 declare ≥ 300 dpi; embedded profiles none 1217, sRGB IEC61966-2.1 478, Adobe RGB (1998) 332, Generic RGB Profile 19.
- Not in the record: 1 vector row (`ADOBE STOCK/girls makeup/~ai-…_.tmp`, a junk name the walk never admits).
