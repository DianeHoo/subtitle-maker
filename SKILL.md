---
name: subtitle-maker
description: Turn a video or raw ASR-generated SRT file into polished, publication-ready subtitles. Use this skill whenever the user has a video (.mov/.mp4/.mkv) and wants subtitles/captions, has a raw SRT from Whisper or any ASR tool and wants it cleaned up or re-segmented, mentions uploading captions to YouTube/Vimeo/social platforms, complains that auto-generated captions are awkward or read poorly, wants to re-cut subtitles by meaning rather than recording pauses, or asks for "better" / "professional" / "clean" subtitles. This skill handles the full pipeline — transcription, multi-signal segmentation, silent self-review across multiple passes, platform-specific adaptation — and only surfaces work to the user when something genuinely needs a human judgment call.
---

# Subtitle Maker

Transform raw video or ASR output into polished, publication-ready subtitles in one controlled pass, with Claude silently self-reviewing against an internal quality checklist so the user only intervenes for the occasional gap.

## Why this skill exists

Auto-generated captions (Whisper, YouTube auto-caption, etc.) segment subtitles by **where the speaker paused**. That's not the same as where the audience reads best. Good subtitles need:

- Semantic coherence (complete phrases/clauses, not mid-thought cuts)
- Natural rhythm (respect breath points — they're a real signal, not noise)
- Screen readability (≤10 words, ≥1s display, no dangling prepositions)
- Platform fit (YouTube needs plain text from 00:00:00; DaVinci keeps style tags; TikTok wants shorter cues)
- Correctness (ASR typos, missing question marks, lowercase "i'm", etc.)

Humans can do this by hand but it's tedious (30+ minutes for 10 minutes of video). This skill collapses that into: transcribe → segment → silent self-review → emit draft → accept user gap-fixes → emit final SRT → platform-adapt.

## Core principle: Claude reviews silently, user finds gaps

The self-review checklist (see `reference/self_review_checklist.md`) is **Claude's internal quality bar**, not a user-facing instruction manual. After generating subtitles:

1. Run the checklist internally across multiple passes
2. Fix everything that's fixable
3. Only flag items to the user where a judgment call is needed (e.g., "is this speaker's filler word 'uh' intentional or noise?")
4. Never hand the checklist to the user as an editing guide — they're not the ones doing the work

The user's job: spot issues Claude's passes missed. Not to apply rules.

## When to invoke

Trigger this skill when any of these signals appear:

- User mentions a video file (.mov/.mp4/.mkv/.avi/.mov) + subtitles, captions, SRT, transcript, or CC
- User provides an existing .srt file and wants it improved / re-segmented / cleaned / re-cut
- User mentions YouTube, Vimeo, TikTok, Instagram captions/subtitles
- User says auto-generated captions are "bad", "awkward", "weird", "break in wrong places"
- User asks to "re-cut subtitles by meaning" or "split by sentence instead of pause"
- User mentions DaVinci Resolve and subtitle import/export
- User wants to translate subtitles (can be chained with an upstream translation step)

## Workflow

### Stage 0: Assess input

Determine what the user gave you:

| Input | Path |
|---|---|
| Video file only | Run Stage 1 (transcribe) then 2 |
| Video + existing SRT | Skip Stage 1, use SRT; optionally cross-check with video if quality matters |
| Raw SRT (Whisper-style) | Skip Stage 1, start at Stage 2 |
| Video + user wants translation | Stage 1 → translate → Stage 2+ |

Ask the user **only** if the input is genuinely ambiguous. Most of the time the file extension tells you.

Also ask the target platform if not stated (YouTube is the safe default for uploads; DaVinci if they mention editing).

### Stage 1: Transcribe (only if input is video)

Use `scripts/transcribe.py`, which wraps WhisperX to get **word-level timestamps** (not just sentence-level like vanilla Whisper). Word-level timestamps are what make downstream re-segmentation possible without time drift.

```bash
python scripts/transcribe.py <video> --output <output.srt> --timeline <timeline.json>
```

Fallback: if WhisperX isn't installed and the user can't install it, use vanilla Whisper and have the script interpolate word timings linearly within each segment. This is lossy but workable.

### Stage 2: Multi-signal segmentation

Use `scripts/segment.py`. Unlike naive 10-word greedy cutting, this scores every potential cut point by combining:

- **Semantic signals**: sentence-end punctuation, clause boundaries, conjunctions, prepositions
- **Pause signals**: where the original ASR put cue boundaries (these encode the speaker's natural breath points — throwing them out loses rhythm info)
- **Rhythm signals**: word count sweet spot (5–8 words), avoid orphan tails
- **Constraint signals**: proper noun pair protection, compound noun protection, hard word-count cap

See `reference/segmentation_algorithm.md` for the scoring table and tuning notes.

Output: an **interactive HTML editor** (`<name>_draft.html`) — one subtitle per card, line numbers outside the cards, Enter splits at cursor, ⌫ at line start merges up, arrow keys navigate across rows. Plus an internal timeline JSON for Stage 4.

If for any reason HTML is unsuitable (headless env, user prefers plain text), pass `--format txt` to get a numbered text draft instead.

### Stage 3: Silent self-review (Claude's main job)

Read `reference/self_review_checklist.md` and apply it to the draft in at least two passes:

- **Pass 1 — Word level + Punctuation**: fix capitalization, contractions, homophones, missing `?`, subject-verb agreement (checklist sections A, B)
- **Pass 2 — Segmentation + Flow**: fix orphan tails, split compound nouns back together, capture natural pause points missed by the algorithm (sections C, E)
- **Pass 3 — Platform + Timing** (during Stage 5 build): ensure platform constraints met (sections D, F)

**Important**: Don't narrate what you found during these passes. Just fix. Only surface items that need a human decision (ambiguous filler words, unclear proper noun spellings, speaker corrections you're not sure about). Aim for ≤3 items flagged; if you have more, you're likely being over-cautious.

Also consult `reference/common_asr_errors.md` for recurring error patterns (falls/follows, bring/brings, their/there, etc.). Each project should grow this file — when the user corrects something in the final review, if it's a pattern worth remembering, append it.

### Stage 4: Present to user

After self-review, open the HTML editor in the user's browser:

```bash
open <name>_draft.html    # macOS
xdg-open <name>_draft.html   # Linux
```

Tell the user briefly:
- Path to the HTML editor (also just opened it)
- Summary: cue count, average/max words per cue, duration
- Any flagged items from Stage 3 that need their decision (keep this list ≤3 items; if you have more, you were over-cautious)
- The editor controls (Enter splits at cursor, Backspace at line start merges up). The hint is already on the page, so no need to repeat in detail.
- "When you're done, click Finish to copy, then paste back into this chat."

Do NOT hand them the self-review checklist or ask them to apply rules. Just: "I've cleaned what I could. Scan for anything that reads wrong — the editor makes splits/merges easy."

### Stage 5: Rebuild SRT from user's paste

When the user pastes the draft back into the chat, save the pasted text to a `.txt` file and run `scripts/build_srt.py`:

```bash
# Typical:
python scripts/build_srt.py <paste>.txt --timeline <timeline.json> --output <final.srt>
```

Save the paste exactly as given — the format the HTML Finish button emits is already compatible (header comments + `NNN  text` numbered lines). build_srt.py strips the leading number and uses each non-empty non-comment line as one SRT cue.

The script aligns the edited draft words back to the word-level timeline via `SequenceMatcher`. Words the user added/changed get timestamps interpolated from neighbors.

### Stage 6: Platform adaptation

Run `scripts/adapt_platform.py` with the target:

```bash
python scripts/adapt_platform.py <final.srt> --target youtube --output <final_youtube.srt>
```

Targets: `youtube` (strip tags, ensure 00:00:00 start), `davinci` (preserve tags), `tiktok` / `instagram` (shorter cues, optional force-split), `broadcast` (optional SMPTE offset).

See `reference/platform_specs.md` for what each target requires.

### Stage 7: Deliver + iterate

Deliver the final file(s) with a brief summary:
- Input type → output files produced
- Cue count, duration range, word stats
- Platform adaptations applied
- Where to find the draft (in case they want to edit further)

**Also include a short "what to do with this SRT" note.** Many users — especially first-timers — don't know what an SRT file is or what to do with it once they have it. Don't assume they do. Pick the 1–3 most relevant downstream actions for their stated platform/use case and give a one-line how-to for each. Don't dump the whole list; be contextual.

Common downstream uses (pick what's relevant):

- **YouTube / Vimeo closed captions**: upload via YouTube Studio → Subtitles → Upload file.
- **Play with subtitles in VLC / IINA**: drop the `.srt` next to the video with the same filename; VLC picks it up automatically.
- **Import into DaVinci / Premiere / Final Cut / iMovie**: File → Import → pick the SRT → drop on a subtitle track.
- **Burn captions into the video permanently** (for TikTok / Instagram / anywhere without closed captions): `ffmpeg -i video.mov -vf subtitles=captions.srt output.mp4`.
- **Translate**: paste SRT into Google Translate / DeepL / Claude — timings stay intact.
- **Search / summarize**: SRT is plain text — grep it, feed to an LLM, pipe to transcript tools.

If they asked for YouTube captions, just tell them the YouTube upload step. If they didn't specify, mention 2–3 common uses so they have options.

If the user comes back with fixes (e.g., "cue 125 is wrong"), edit the **draft** file and re-run Stages 5–6. Don't edit the SRT directly — the draft is the source of truth. This keeps everything in sync.

## Key files in this skill

```
subtitle-maker/
├── SKILL.md                              (this file — workflow overview)
├── scripts/
│   ├── transcribe.py                     (Stage 1: WhisperX wrapper)
│   ├── segment.py                        (Stage 2: multi-signal segmentation → HTML editor)
│   ├── build_srt.py                      (Stage 5: draft → SRT with alignment)
│   └── adapt_platform.py                 (Stage 6: per-platform adjustments)
├── templates/
│   └── editor.html                       (HTML editor template — segment.py fills TITLE + SAMPLE)
├── reference/
│   ├── self_review_checklist.md          (Stage 3 internal checklist — primary IP)
│   ├── common_asr_errors.md              (error patterns to look for)
│   ├── segmentation_algorithm.md         (scoring table + tuning notes)
│   └── platform_specs.md                 (what each target needs)
└── examples/
    └── README.md                         (reference cases)
```

## Edge cases and gotchas

- **Multi-speaker content (Q&A, interviews)**: each speaker's section still processes the same way, but watch for crossovers. Speaker labels (`SPEAKER 1:`) if the ASR provides them should be preserved.
- **Music / applause / non-speech**: WhisperX sometimes misidentifies. Leave `[MUSIC]` / `[APPLAUSE]` markers intact; treat as standalone cues.
- **Numbers and dates spoken differently from written**: "two thousand nineteen" vs "2019" — prefer the written numeric form in subtitles for readability. This is a judgment call.
- **Speaker corrections mid-sentence** ("...I mean, actually..."): preserve unless they're clearly throwaway fillers. Err toward keeping.
- **Very long sentences with no punctuation in source**: the segmentation algorithm can't invent semantic structure that isn't there. Flag these to the user as "source had no punctuation here — here's my best guess, please verify." Don't silently hallucinate sentence boundaries.
- **Proper nouns the ASR got wrong**: if the user tells you the correct spelling, also check `reference/common_asr_errors.md` to see if it's a known pattern; if not, consider appending it.

## What NOT to do

- Don't hand the user `self_review_checklist.md` as an editing guide. It's for Claude.
- Don't skip Stage 3's self-review passes to save time. Those passes are the whole point — skipping them means the user has to do your job.
- Don't edit `<final>.srt` directly when fixing issues. Edit the draft and regenerate.
- Don't assume the user wants YouTube format. Ask if unsure.
- Don't invent sentence boundaries in run-on transcripts without flagging. Guessing silently is worse than flagging.
- Don't narrate every single fix you made during self-review. The user doesn't care about "I capitalized 15 I'ms." They care about the output.
