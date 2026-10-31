# WATCH intake — external video knowledge base

Purpose: give the Design OS a curated, provenance-backed knowledge base of real-world
craft in three domains, distilled from video sources via the `/watch` plugin
(yt-dlp + ffmpeg frames + native captions; Whisper fallback optional, currently keyless).

This serves the standing ruling that measurements are inputs and creativity is the
point: generation runs must be able to consult real reference craft, not guesses.

## Domains

| Dir | Domain |
|---|---|
| `cosmetics_packaging/` | Bottle/jar/label design language, luxury vs. mass positioning, brand systems on packaging |
| `dielines_structure/` | Dieline construction, folding cartons, wrap geometry, print-ready structure |
| `print_finishing/` | Foils, embossing/debossing, varnish, substrates, label application — the craft layer §L cares about |

## Note format (one file per watched video)

Filename: `<domain>/<slug>.md`. Required sections:

1. **Source** — title, channel, URL, duration, watch date, transcript source
   (`captions` / `whisper` / `frames-only`), detail mode used.
2. **Claims** — numbered, each with a `t=MM:SS` timestamp anchor. A claim without a
   timestamp is not admissible as engine input.
3. **Engine hooks** — which OS components each claim could inform (e.g. dieline
   generator, label sheet, VQR rubric dimensions), stated as suggestions, not rulings.
4. **Limits** — what the video does NOT establish; conflicts with existing authorities.

## Provenance rules (§W-style)

- Every claim cites URL + timestamp. No timestamp → no claim.
- Video content is **evidence, not authority**. Nothing here overrides committed
  rulings, the acceptance rubric, or owner-reserved categories. If a video
  contradicts a committed authority, record the conflict under **Limits** and leave
  the authority standing.
- Queue statuses are honest: `queued` → `watched` → `distilled`. A video is
  `distilled` only when its note file exists with all four sections.

## Runner notes

- Sandbox needs `export PATH="$HOME/.local/bin:$PATH"` for yt-dlp (each bash call).
- Script: `<plugin_root>/skills/watch/scripts/watch.py "<url>" --detail <mode>`.
- Prefer captioned videos < 10 min; use `--detail transcript` first, then targeted
  frames (`--timestamps` / `--max-frames`) only where visuals carry the content.
- No Whisper key is configured; caption-less videos come back frames-only — either
  skip them or add a Groq key later.
