# Common ASR Errors

Patterns observed across projects where ASR (Whisper, YouTube auto-caption, others) consistently gets things wrong. Scan any draft for these before presenting to the user.

This file should grow over time — when the user corrects something that fits a generalizable pattern, add it here.

## Homophones

These sound identical or nearly so, and ASR picks the wrong one based on language model priors. Context usually makes the right choice obvious to a human but not to the ASR.

| ASR often outputs | Should check for | When to use which |
|---|---|---|
| `there` | `their` / `they're` | `their` = possessive; `they're` = contraction of "they are" |
| `its` | `it's` | `it's` = "it is / it has"; `its` = possessive |
| `your` | `you're` | `you're` = "you are" |
| `then` | `than` | `than` = comparison (faster than); `then` = time/sequence |
| `to` | `too` / `two` | `too` = also/excessive; `two` = number |
| `affect` | `effect` | `affect` = verb; `effect` = noun (most of the time) |
| `accept` | `except` | `accept` = receive; `except` = exclude |
| `principal` | `principle` | `principal` = main person/thing; `principle` = rule/tenet |
| `write` | `right` | context |
| `hear` | `here` | context |
| `weather` | `whether` | context |
| `loose` | `lose` | `lose` = verb (to lose); `loose` = adjective (not tight) |

## Near-misses (similar-sounding, different meaning)

These are not true homophones but close enough that Whisper confuses them, especially with accented speech or compressed audio.

| ASR outputs | Likely meant |
|---|---|
| `falls along` | `follows along` |
| `falls through` | `follows through` |
| `brought` | `bought` (or vice versa) |
| `quite` | `quiet` (or vice versa) |
| `breath` | `breathe` |
| `advice` | `advise` (noun vs verb) |
| `loose` | `lose` |
| `of` | `have` (after modals: "could of" → "could have") |
| `would of / could of / should of` | `would have / could have / should have` |

## Subject-verb agreement (phonetic)

ASR transcribes literally from sound, so `-s` endings on verbs can be missed or hallucinated. Check that singular subjects pair with `-s` verbs and plural with bare verbs.

| Wrong | Right |
|---|---|
| `The agent bring these ideas` | `brings` |
| `People is excited` | `are` |
| `Data shows` (when speaker said "data show") | either may be correct — check context |

## Contractions lost

ASR sometimes outputs the expanded form when the speaker clearly contracted. For natural read-ability in subtitles, prefer contractions when the speaker used them.

| ASR | Better |
|---|---|
| `I am going to` (when speaker said "I'm gonna") | `I'm going to` or `I'm gonna` |
| `it is` | `it's` |
| `they are` | `they're` |

## Contractions mis-split

The reverse: ASR fuses contractions as separate tokens without apostrophe.

| ASR | Right |
|---|---|
| `i m` / `i'm` (lowercase) | `I'm` |
| `dont` | `don't` |
| `wont` | `won't` |
| `cant` | `can't` |
| `youre` | `you're` |
| `theyre` | `they're` |
| `its` (when meaning "it is") | `it's` |

## Duplicate words

ASR occasionally doubles a word, especially short function words at segment boundaries.

| ASR | Likely | Judgment |
|---|---|---|
| `the the X` | `the X` | Almost always a dup to remove |
| `and and` | `and` | Same |
| `is is` | `is` | Same |
| `very very` | `very very` or `very` | Preserve if clearly emphatic; remove if clearly stutter |
| `I I think` | `I think` | Remove the dup |

## Missing question marks

This is the single most common punctuation error. ASR rarely adds `?` based on intonation. Scan for question patterns and add:

**Triggers** (cue likely needs `?`):
- Starts with: what / who / when / where / why / how / which
- Starts with auxiliary + subject: do you / does he / did they / is it / are we / can I / could you / will you / would he / should we / have you / has she / had they
- Ends with tag question: `..., right?` / `..., isn't it?` / `..., don't you?`
- Is a rhetorical setup: `You know what X is?` / `Does that make sense?`

## Missing periods (run-on merges)

Whisper will often run multiple sentences together without a period, especially when the speaker doesn't pause between them. Scan for:

- A capitalized word mid-cue that looks like a sentence start (`...leadership She says...` → `...leadership. She says...`)
- Change of subject mid-phrase with no punctuation
- `, so` / `, but` / `, and` used to glue two independent clauses that could stand alone

When adding a period, also capitalize the following word.

## Numbers and dates

ASR output varies:
- `twenty nineteen` vs `2019` — prefer the numeric form for subtitles (shorter, more scannable)
- `three hundred and fifty` vs `350` — prefer numeric unless it's at the start of a sentence (where style guides often prefer words)
- `CHI 2026` — preserve as written (proper noun + numeric)

## Named entities

ASR frequently mangles:
- Names of people (especially non-English names)
- Company names and product names
- Place names (uncommon cities, universities)
- Technical terms and acronyms

When the user gives you the correct spelling of a named entity, apply it consistently across all occurrences in the draft (use find-and-replace if many).

## Project-specific patterns

Append new patterns here when you encounter them. Include the ASR output, the correction, and brief context.

### Example entries (template)

```
- `falls along` → `follows along` (common Whisper error on this phrase)
- `i'm` (lowercase) → `I'm` (Whisper sometimes outputs lowercase mid-sentence)
- `spilled` → `built` (context-dependent verb mishearing)
```
