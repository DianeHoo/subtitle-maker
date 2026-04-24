# Segmentation Algorithm

The multi-signal scoring approach used by `scripts/segment.py`. Understanding this helps tune it for specific content types.

## Core idea

Naive approaches (e.g., "cut every 10 words" or "cut at every comma") produce awkward subtitles because they ignore the interplay of signals. A good cut satisfies multiple criteria simultaneously.

The algorithm scans left-to-right through a word-level timeline. At each position, it computes a **cut score**. When score ≥ threshold AND minimum-words constraint is met, it cuts.

## Signals and weights

| Signal | Weight | Notes |
|---|---|---|
| Prior word ends in `.?!` | +5 (forced) | Sentence-end — always cut (unless abbreviation) |
| Prior word ends in `,;:` | +2 | Mid-sentence boundary |
| Current position has original ASR pause | +2 | Whisper/ASR put a cut here — respect the breath |
| Current word is a conjunction (and/but/so/or) | +1 | Cut BEFORE conjunctions |
| Current word is a subordinator (that/which/when/because) | +0.8 | Cut BEFORE subordinators |
| Current word is a preposition (in/on/to/of/for/with/by/from) | +0.5 | Cut BEFORE preposition phrases (weaker signal) |
| Accumulated words ≥ 7 | +0.3 per additional word | Encourage cuts in sweet-spot range |
| Would split a proper noun pair (Title Title) | -5 | Veto |
| Would split a known compound (future prospect) | -4 | Strong veto |
| Would leave ≤2 word orphan before next sentence end | -3 | Prefer balancing |
| Prior word is article/preposition (dangling) | -2 | Avoid ending on "the" / "a" / "of" |
| Accumulated words ≥ 10 | +∞ (forced) | Hard cap — cut no matter what |

**Threshold**: Default 2.5. Tunable per project.

## Algorithm skeleton

```
scores = compute_scores_at_each_position(words)
cuts = []
start = 0
for i in range(1, len(words)):
    words_so_far = i - start
    if words_so_far >= 10:                          # hard cap
        cuts.append(i); start = i; continue
    if words_so_far < 3:                            # minimum 3 words
        continue
    if scores[i] >= 2.5:
        cuts.append(i); start = i
```

## Why these signals?

**Sentence terminators (+5)**: Obvious — end of thought, always a good cut point.

**Mid punctuation (+2)**: Commas/colons are where the writer (or the speaker's transcription) inserted a pause explicitly. Respecting these keeps the subtitle rhythm aligned with reading rhythm.

**Original pause points (+2)**: This is the signal naive semantic segmenters miss. When Whisper output a cut, it's because the speaker paused. The pause carries information — where they broke for breath, where they thought a new idea began. Throwing this out means Claude's re-segmentation can land on grammatically valid but *rhythmically wrong* cuts.

**Conjunctions and subordinators (+1, +0.8)**: `and`, `but`, `so`, `that`, `which` — these begin new clauses. Cutting before them preserves clause integrity in each cue.

**Prepositions (+0.5)**: Weaker because prepositional phrases often belong with the verb they follow (`in 2019` with `happened`). But between two equally long cue candidates, cutting at a preposition boundary reads slightly better than mid-phrase.

**Word-count encouragement (+0.3/word after 7)**: Pushes toward the 7–10 range when no other signal fires. Otherwise the algorithm would keep extending cues to 10 words every time just because no cut was "good enough".

**Proper noun pair veto (-5)**: `Silicon Valley`, `Carnegie Mellon`, `New York City` — cutting between title-cased adjacent tokens produces visually jarring subtitles.

**Compound noun veto (-4)**: Harder to detect automatically. Maintain a list of known compounds for your content domain (see `common_compounds.md` if you have one; otherwise hardcode project-specific ones in the script).

**Orphan avoidance (-3)**: If cutting here would leave only 1–2 words before the next forced cut (sentence end), it's usually better to pull the cut back one step so both pieces are more balanced.

**Dangling article/preposition (-2)**: Ending a cue with `the` or `of` makes the next cue start abruptly. Penalize these.

## Tuning for content type

Different content benefits from different thresholds:

| Content | Threshold | Max words | Notes |
|---|---|---|---|
| Academic talk / presentation | 2.5 | 10 | Default |
| Casual conversation / podcast | 2.0 | 10 | Lower threshold — more cuts, shorter cues feel natural |
| News / broadcast | 3.0 | 10 | Fewer, longer cues; match broadcast pacing |
| TikTok / Reels | 2.0 | 5 | Many short cues for quick visual rhythm |
| Instructional / tutorial | 2.5 | 8 | Tighter cap to keep reader focused |

## When the algorithm is wrong

The algorithm will be wrong sometimes. Typical failure modes:

1. **Run-on source text**: Speaker rushed through with no punctuation. The algorithm fires on prepositions and conjunctions, producing cuts that look fine individually but feel arbitrary. **Fix**: After segmentation, scan for these and manually rebalance. Long term: add more compound nouns to the veto list.

2. **Short-sentence dense speaker**: Some speakers deliver in 3–4 word bursts. The algorithm may join them into one cue because each burst is short. **Fix**: Lower threshold to ~2.0 for such speakers.

3. **Multi-language / code-switching**: Scoring assumes English grammar cues. For multilingual content, revisit signals per language.

4. **Technical content with jargon compounds**: `monte carlo tree search`, `generative adversarial network` — treat as compounds. Add to the script's compound list.

## After segmentation: the self-review step matters

Don't rely on the algorithm being perfect. The self-review pass (see `self_review_checklist.md`) catches:
- Missed proper nouns (add commas or restructure)
- Dangling prepositions that slipped past the penalty
- Orphans that balancing didn't catch

Think of segmentation as "get 85% of the way there" and self-review as "take it to 95%." The remaining 5% is what the user scans for.
