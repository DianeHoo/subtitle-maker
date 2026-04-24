# Self-Review Checklist

This is Claude's internal quality bar for subtitle review. Apply it silently across multiple passes after generating a draft. Do not hand this file to the user as an editing guide — they're not doing the work, you are.

The sections below are organized by concern. In practice, do Pass 1 on word-level + punctuation (A, B), Pass 2 on segmentation + flow (C, E), Pass 3 during build for timing + platform (D, F).

---

## A. Word-level correctness

Every subtitle must be *right* at the word level before anything else matters.

### A1. Capitalization

- **Sentence-initial words**: after any `.?!`, next word starts uppercase. ASR almost always gets this wrong after missing periods.
- **First-person "I"**: always uppercase. `I / I'm / I'll / I've / I'd / I's` (rare but possible).
- **Proper nouns**: names, places, brands, products, paper titles. ASR inconsistently capitalizes these. If the user tells you a project-specific proper noun spelling, apply consistently across all occurrences.
- **Titles and honorifics**: `Dr.`, `Mr.`, `Prof.`, `CEO`, `HR` — uppercase the abbreviations; `doctor` is lowercase unless sentence-initial.

### A2. Contractions

ASR often renders contractions as separate words or loses the apostrophe. Check:
- `I m` → `I'm`
- `dont / wont / cant` → `don't / won't / can't`
- `its` vs `it's` — the latter = "it is / it has"; the former = possessive
- `youre / youll / youve` → `you're / you'll / you've`
- `theyre / theyd / theyve` → `they're / they'd / they've`

### A3. Subject-verb agreement

ASR transcribes phonetically, so homophonous verb forms often end up wrong:
- `The agent bring these two ideas` → `brings` (singular subject)
- `People is talking` → `are`
- `The data shows` vs `The data show` — judgment call; prefer whatever matches the speaker's clear intent

### A4. Common homophones (ASR misidentifies)

Scan for these specifically — they're the top offenders:

| Often wrong | Should be |
|---|---|
| `their` / `there` / `they're` | context-dependent |
| `its` / `it's` | possessive vs contraction |
| `to` / `too` / `two` | direction / also / number |
| `your` / `you're` | possessive vs contraction |
| `then` / `than` | time vs comparison |
| `affect` / `effect` | verb vs noun |
| `falls` / `follows` | literally similar sounds |
| `accept` / `except` | sound-alikes |
| `write` / `right` | verb vs direction/correct |
| `principal` / `principle` | person vs concept |

See `common_asr_errors.md` for a growing project-level list.

### A5. Repeated words and filler

- **Stutter/repeat artifacts**: "the the left" → "the left", "very very cool" → keep if intentional emphasis, remove if clearly a stutter. Judgment call — err toward keeping if ambiguous.
- **Filler words** (`uh`, `um`, `you know`, `like`, `I mean`): preserve if they're part of the speaker's voice and the content is informal. Remove if they genuinely add nothing. For formal presentations, lean toward removing.
- **Speaker corrections** ("I mean, actually..."): preserve unless clearly throwaway.

---

## B. Punctuation

### B1. Sentence terminators

Every declarative sentence ends with `.`. Every interrogative with `?`. Every emphatic with `!` (use sparingly). ASR output frequently has missing terminators — especially `?` on questions that trail off or use rising intonation without explicit question words.

**Heuristic for spotting missing terminators**: if the next cue starts with a capitalized word AND the previous cue ends with no punctuation AND the words flow as if continuing, the sentence terminator is almost certainly missing. Add it.

Handle abbreviations correctly: `Dr.`, `Mr.`, `Mrs.`, `Ms.`, `St.`, `vs.`, `etc.`, `Inc.`, `Ltd.`, `Jr.`, `Sr.`, `e.g.`, `i.e.` — these aren't sentence ends.

### B2. Commas

- **List separators**: `a, b, and c` or Oxford-comma style `a, b, c`. Pick one and stay consistent.
- **Clause boundaries**: before coordinating conjunctions in compound sentences (`..., and ...`) when clauses are long.
- **After introductory phrases**: `Importantly,` / `In fact,` / `Secondly,` — always followed by comma.
- **Around appositives**: `Jane Doe, a researcher at State University, ...`

### B3. Question marks specifically

ASR consistently misses these. Check for question-indicating patterns:
- Starts with question word (what/who/when/where/why/how/do/does/did/is/are/can/could/will/would)
- Rising intonation (hard to detect in text, so rely on semantic cues)
- Tag questions (`..., right?` / `..., isn't it?`)

If in doubt and context suggests a question was asked, add the `?`.

### B4. Missing sentence boundaries

When ASR runs multiple sentences together without periods, the multi-signal segmentation tries to detect them. After segmentation, scan for signs of a missed boundary:
- Adjacent words where the second starts a new clause (e.g., `leadership She says` → `leadership. She says`)
- A cue that reads as two merged sentences
- Capitalization jumping mid-phrase

---

## C. Segmentation

### C1. Word count

- **Hard cap**: ≤10 words per cue by default. Configurable (some TikTok/IG contexts want ≤5).
- **Sweet spot**: 3–7 words. Much shorter than 3 reads choppy; much longer strains reading speed.
- **Minimum**: 1 word only for genuine standalone utterances (`Thank you.`, `Yes.`, `No?`). Don't artificially pad.

### C2. Don't split these

- **Proper noun pairs/chains**: `Silicon Valley`, `New York City`, `Carnegie Mellon`, multi-word paper/product names. Use the title-case adjacency heuristic: if two consecutive title-cased tokens would be split by a cut, move the cut elsewhere.
- **Compound nouns**: `future prospect`, `intent drift`, `trust paradox`, `design fiction` — these function as single semantic units in the speaker's phrasing.
- **Preposition + object phrases**: `in 2019`, `from the office`, `to the team` — ideally stay together unless the phrase itself is long.

### C3. Don't end a cue with

- A dangling preposition if it separates from its object (`a good balance of` — bad if next cue starts `how`)
- A dangling article (`the`, `a`, `an`) with its noun on the next cue
- A dangling auxiliary (`will`, `was`, `have`) separated from the main verb
- A conjunction (`and`, `but`, `so`) — these belong at the start of the next cue, not the end of the current

### C4. Orphan tails

- Avoid leaving 1–2 words dangling at the end of a sentence when the prior cue has room. Re-balance by pulling an earlier word back or pushing forward a later word.
- If a tail is genuinely ≤2 words and can't be merged (e.g., it's the only way to show the sentence end), that's fine.

### C5. Respect original pause points

The raw ASR cue boundaries encode **where the speaker actually paused**. These are real rhythm signals — don't throw them out.

When scoring cut candidates during segmentation, give the original pause positions a bonus. When self-reviewing, if you're tempted to move a cut point, check first: was the original pause-based cut actually fine? If two different cuts are equally valid semantically, prefer the one that aligns with a natural breath.

---

## D. Timing

### D1. Per-cue duration

- **Minimum display time**: ~1 second (below this, reader can't catch it — even for 2-word cues)
- **Maximum display time**: ~7 seconds (above this, reader re-reads; the subtitle should have split)
- If a cue hits the minimum because the speaker talks very fast, it's fine — just make sure cues don't overlap when you expand

### D2. Cue ordering

- Start times must be monotonically non-decreasing
- Each cue's end > its start
- No overlap: `cue[i].end <= cue[i+1].start` (equality is fine — back-to-back)
- Gaps between cues are OK — they represent silence/pauses. Don't artificially fill.

### D3. First and last cues

- **First cue**: starts at or very near `00:00:00,000`. If the first word of the video is spoken at `00:00:02`, first cue starts there (or slightly earlier for comfortable read-in).
- **Last cue**: ends at or before the video's actual duration. Don't extend past the end of the video.

---

## E. Flow

### E1. Coherent adjacency

Read each pair of adjacent cues as if they were spoken by a person. If the transition sounds natural, the cut is good. If there's a "wait, what?" moment, the cut is wrong even if it technically passes all the rules above.

This is the most subjective part of the review. Apply judgment.

### E2. Independent utterances

Short standalone phrases get their own cue:
- `Thank you.`
- `Yes, indeed.`
- `No?` / `Sure.` / `Really?`
- Speaker addresses: `Alex, please take over.`
- Short questions inviting response: `Got it?`

Don't merge these with surrounding content just to hit a word-count target.

### E3. Parallel structure

When the speaker uses parallel phrasing ("efficiency and control" / "trust, fairness, and accountability" / "short-term, long-term, lifetime"), keep the parallel items in the same cue when possible, or split them consistently (one item per cue).

---

## F. Platform adaptation

### F1. YouTube (primary default)

- Strip all style tags (`<b>`, `<font color=...>`, `<i>`) — YouTube either ignores them or renders them incorrectly
- Start at `00:00:00,000` (the video's playback time, not SMPTE)
- UTF-8 encoding, no BOM
- Standard SRT format only — no WebVTT cues

### F2. DaVinci Resolve (editing)

- Preserve `<b>` and `<font color=...>` tags if the editor wants styling
- Timecode should match the editing timebase (typically 00:00:00 start unless the edit offsets)

### F3. TikTok / Instagram Reels

- Much shorter cues (2–5 words ideal)
- Faster pacing (higher cues-per-minute)
- Consider burned-in rendering: if burning in, ensure contrast and position work with the video

### F4. Broadcast / Professional

- SMPTE timecode may start at 01:00:00:00 (1 hour preroll convention)
- Frame-accurate timing (check frame rate)
- May need caption CEA-608/708 format, not SRT

### F5. Translation workflows

- If subtitles will be translated, keep cues as independent semantic units (1 cue = 1 translatable thought)
- Avoid sentences that span multiple cues unless unavoidable
- Keep original language SRT as the master; generate translations as parallel files

---

## Flagging items to the user

After self-review passes, you may have items you genuinely cannot resolve:

- Ambiguous filler words (keep "uh" or remove?)
- Proper noun spellings you're unsure about
- Speaker corrections where preserving vs removing is subjective
- Source run-ons where you had to guess sentence boundaries

Flag these as a bulleted list at the end of your stage 4 output. Keep the list short (ideally ≤3 items). If you're flagging more than 3, you're probably being over-cautious — make more decisions yourself.

Format flags as: "Cue N: [what's uncertain] — I chose X; let me know if you want Y."

## Review completion criteria

A draft is ready to present to the user when:
- All A-E checks pass
- F checks will pass after Stage 6 platform adapter runs
- Any items you couldn't resolve are listed as flags

Do not present a draft where you haven't run the checklist. The whole point of this skill is that Claude does the review work, not the user.
