# Platform Specifications

Requirements and conventions for each target platform. Pass the target to `scripts/adapt_platform.py`.

## youtube

YouTube's subtitle upload (via Studio or API) accepts standard SRT.

**Requirements:**
- **Format**: SRT (`.srt`)
- **Encoding**: UTF-8 (no BOM)
- **Timecode**: Starts at `00:00:00,000` — YouTube uses the video's playback time, NOT any SMPTE timecode embedded in the source video. If your video has an internal `01:00:00:00` start (broadcast convention), the subtitle still starts at `00:00:00,000`.
- **Styling**: Strip all HTML-like tags (`<b>`, `<i>`, `<font color=...>`). YouTube either ignores them silently or renders them inconsistently across browsers.
- **Line length**: Soft limit ~42 characters per displayed line. Long cues may wrap awkwardly on mobile.
- **Cue count**: No hard limit, but extremely many short cues (<0.5s) may be filtered.

**Avoid:**
- WebVTT-specific cues (NOTE, STYLE blocks) — use .vtt instead if you need those
- Positioning/styling within cues — YouTube doesn't respect them

## davinci

For editing in DaVinci Resolve's Fairlight or Edit page subtitle track.

**Requirements:**
- **Format**: SRT (`.srt`)
- **Encoding**: UTF-8
- **Timecode**: Match the editing timebase — if the edit starts at 00:00:00, SRT starts at 00:00:00
- **Styling**: Preserve `<b>` and `<font color='#RRGGBB'>` tags — DaVinci reads these and applies them to subtitle text
- **Frame rate awareness**: SRT uses millisecond precision; DaVinci will quantize to frames. If the edit is 23.976fps, don't worry about sub-frame precision.

## tiktok / instagram-reels

Short-form vertical video platforms. Usually burned-in captions (baked into the video), but the SRT serves as the source of truth for that burn-in.

**Requirements:**
- **Cue length**: Much shorter — 2–5 words per cue, sometimes 1–3 for emphasis
- **Cues per minute**: High — 30–60 cues per minute is normal for burned-in style
- **Duration**: Each cue 0.5–2 seconds typically
- **Styling**: For burned-in, style is set at the burn step, not in SRT
- **Timing**: Start at 00:00:00

**Adaptation**: If the input draft has longer cues, re-segment with a tighter word cap (pass `--max-words 5` to segment.py).

## vimeo

Similar to YouTube but slightly more permissive on styling.

**Requirements:**
- **Format**: SRT or WebVTT
- **Encoding**: UTF-8
- **Timecode**: 00:00:00 start
- **Styling**: Basic tags (`<b>`, `<i>`) supported; avoid font color (inconsistent rendering)

## broadcast

Professional broadcast (linear TV, streaming platforms with broadcast lineage).

**Requirements:**
- **Format**: Often CEA-608 / CEA-708 captions, not SRT. This skill doesn't natively produce CEA formats — use a separate conversion tool.
- **Timecode**: Often starts at `01:00:00:00` SMPTE (1 hour preroll is broadcast convention to handle leader/countdown). The SRT times should be offset accordingly.
- **Frame accuracy**: Subtitles must align to frame boundaries. Specify the frame rate when adapting.
- **Line length**: Strict — typically ≤32 characters per line, max 2 lines per cue

**Adaptation**: Pass `--target broadcast --smpte-offset 01:00:00:00 --fps 23.976` to apply SMPTE offset and frame quantization.

## webvtt

For HTML5 `<track>` element usage.

**Requirements:**
- **Format**: WebVTT (`.vtt`) — NOT SRT
- **Encoding**: UTF-8
- **Header**: File starts with `WEBVTT\n\n`
- **Timecode**: Uses `HH:MM:SS.mmm` (period, not comma)
- **Styling**: Supports CSS via `::cue` selector — preserve class tags if used

**Adaptation**: Pass `--target webvtt`. The adapter will convert timestamp delimiters and add the header.

## generic / archival

If you don't know the target yet, produce a clean vanilla SRT with:
- No styling tags
- UTF-8 encoding
- 00:00:00 start
- Standard SRT format

This can be consumed by any downstream tool.

---

## Adapter output naming

By convention, the adapter appends the target to the filename:

```
final.srt                  → final_youtube.srt
final.srt                  → final_davinci.srt
final.srt                  → final_tiktok.srt
final.srt                  → final.vtt         (webvtt changes extension too)
```

The user can override with `--output <path>`.
