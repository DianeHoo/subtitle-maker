#!/usr/bin/env python3
"""Multi-signal segmentation: take a raw SRT (or timeline JSON) and re-cut into
subtitle-friendly segments using semantic + pause + rhythm signals.

Usage:
    # From a raw SRT (interpolates word timings internally):
    python segment.py input.srt --output draft.txt --timeline timeline.json

    # From a timeline JSON (preferred — precise word timings):
    python segment.py --timeline-in input_timeline.json --output draft.txt --timeline timeline.json

    # Tune thresholds:
    python segment.py input.srt --max-words 8 --threshold 2.0 --output draft.txt

Output:
    - draft.txt: plain-text draft, one subtitle per line, numbered
    - timeline.json: enriched word-level timeline with pause_after flags, for later build_srt.py

See reference/segmentation_algorithm.md for algorithm details.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


# -------- SRT parsing --------

def parse_srt(path: str):
    """Return list of (start_ms, end_ms, text_with_tags_stripped)."""
    with open(path, encoding="utf-8") as f:
        data = f.read()
    blocks = re.split(r"\n\s*\n", data.strip())
    entries = []
    for b in blocks:
        lines = [ln for ln in b.splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        m = re.match(
            r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})",
            lines[1],
        )
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
        start = h1 * 3600000 + m1 * 60000 + s1 * 1000 + ms1
        end = h2 * 3600000 + m2 * 60000 + s2 * 1000 + ms2
        text = " ".join(lines[2:])
        text = re.sub(r"</?b>", "", text)
        text = re.sub(r"</?i>", "", text)
        text = re.sub(r"<font[^>]*>", "", text)
        text = re.sub(r"</font>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        entries.append((start, end, text))
    return entries


def srt_to_word_timeline(entries):
    """Interpolate word timings linearly within each SRT cue. Marks pause_after on cue boundaries."""
    words = []
    for i, (s, e, t) in enumerate(entries):
        is_last = i == len(entries) - 1
        toks = t.split()
        if not toks:
            continue
        step = (e - s) / len(toks)
        for j, w in enumerate(toks):
            pause_after = (j == len(toks) - 1 and not is_last)
            words.append({
                "word": w,
                "start_ms": int(s + j * step),
                "end_ms": int(s + (j + 1) * step),
                "pause_after": pause_after,
            })
    return words


# -------- Text heuristics --------

STARTER_WORDS = (
    r"(And|But|So|We|They|It|This|That|Then|However|Also|Or|Now|Here|There|He|She)"
    r"(?:'s|'re|'ll|'d|'m|'ve)?\b"
)
STARTER_RE = re.compile(r"^" + STARTER_WORDS)
ABBREV = {
    "Dr.", "Mr.", "Mrs.", "Ms.", "St.", "vs.", "etc.", "Inc.", "Ltd.",
    "Jr.", "Sr.", "e.g.", "i.e.", "U.S.", "U.K.", "Ph.D.", "Prof.",
}
SENT_END = re.compile(r"[.?!]$")
MID_PUNC = re.compile(r"[,;:]$")

CONJUNCTIONS = {"and", "but", "so", "or", "yet", "for", "nor"}
SUBORDINATORS = {
    "that", "which", "when", "where", "because", "if", "while", "whereas",
    "although", "though", "since", "until", "unless", "after", "before",
    "whether", "as",
}
PREPOSITIONS = {
    "in", "on", "at", "to", "of", "for", "with", "by", "from", "into",
    "about", "than", "through", "over", "under", "between", "among",
}
ARTICLES = {"the", "a", "an"}
AUX = {"will", "would", "could", "should", "have", "has", "had", "is",
       "are", "was", "were", "be", "been", "being", "do", "does", "did"}

# Known compounds (veto splits between these)
KNOWN_COMPOUNDS = [
    ("future", "prospect"),
    ("intent", "drift"),
    ("trust", "paradox"),
    ("design", "fiction"),
    ("Silicon", "Valley"),
    ("New", "York"),
    ("Carnegie", "Mellon"),
]
KNOWN_COMPOUNDS_SET = {c for c in KNOWN_COMPOUNDS}


def strip_punct(w: str) -> str:
    return re.sub(r"[^\w']", "", w)


def is_sent_end(w: str) -> bool:
    return bool(SENT_END.search(w)) and w not in ABBREV


def is_mid_punc(w: str) -> bool:
    return bool(MID_PUNC.search(w))


def is_title_case(w: str) -> bool:
    s = strip_punct(w)
    return bool(s) and s[0].isupper() and s.lower() not in {"i", "i'm", "i'll", "i've", "i'd"}


def inject_missing_sentence_boundaries(words):
    """If a word ends lowercase and the next word starts with a sentence-starter, add '.' to current.
    This catches missing periods in run-on transcripts."""
    for i in range(len(words) - 1):
        w = words[i]["word"]
        nxt = words[i + 1]["word"]
        if re.search(r"[.?!,;:]$", w):
            continue
        if not re.search(r"[a-z0-9]$", w):
            continue
        if STARTER_RE.match(nxt):
            words[i]["word"] = w + "."
    return words


# -------- Scoring --------

def compute_cut_score(words, i, words_since_cut):
    """Score a potential cut BEFORE position i (i.e., after word i-1).
    Higher score = better cut point."""
    if i == 0 or i >= len(words):
        return -10.0  # can't cut at start/end

    prev_w = words[i - 1]["word"]
    cur_w = words[i]["word"]

    score = 0.0

    # Sentence end (forced cut — handled separately in segmenter)
    if is_sent_end(prev_w):
        return 100.0

    # Mid punctuation
    if is_mid_punc(prev_w):
        score += 2.0

    # Original ASR pause point
    if words[i - 1].get("pause_after"):
        score += 2.0

    # Current word is a conjunction (cut before)
    if strip_punct(cur_w).lower() in CONJUNCTIONS:
        score += 1.0

    # Current word is a subordinator
    if strip_punct(cur_w).lower() in SUBORDINATORS:
        score += 0.8

    # Current word is a preposition
    if strip_punct(cur_w).lower() in PREPOSITIONS:
        score += 0.5

    # Encourage cuts in sweet spot (7-10 words)
    if words_since_cut >= 7:
        score += 0.3 * (words_since_cut - 6)

    # Veto: splitting a title-cased pair (proper noun)
    if is_title_case(prev_w) and is_title_case(cur_w) and not re.search(r"[.?!,;:]$", prev_w):
        score -= 5.0

    # Veto: splitting a known compound
    prev_clean = strip_punct(prev_w)
    cur_clean = strip_punct(cur_w)
    if (prev_clean, cur_clean) in KNOWN_COMPOUNDS_SET:
        score -= 4.0
    # also case-insensitive check
    if (prev_clean.lower(), cur_clean.lower()) in {
        (a.lower(), b.lower()) for a, b in KNOWN_COMPOUNDS
    }:
        score -= 4.0

    # Penalty: ending cue on dangling article/aux/prep
    if strip_punct(prev_w).lower() in ARTICLES:
        score -= 2.0
    if strip_punct(prev_w).lower() in PREPOSITIONS:
        score -= 1.0
    if strip_punct(prev_w).lower() in AUX:
        score -= 1.0

    # Penalty: ending cue on conjunction
    if strip_punct(prev_w).lower() in CONJUNCTIONS:
        score -= 2.0

    return score


def segment(words, max_words=10, min_words=3, threshold=2.5):
    """Scan words and produce list of (start_idx, end_idx) cue boundaries."""
    cues = []
    start = 0
    i = 1
    while i < len(words):
        wsc = i - start

        # Forced cut: sentence end on prior word
        if is_sent_end(words[i - 1]["word"]):
            cues.append((start, i))
            start = i
            i += 1
            continue

        # Forced cut: hard cap
        if wsc >= max_words:
            # Look backward for a better cut within the range
            best_cut = i
            best_score = -10
            for k in range(max(start + min_words, i - max_words + 1), i + 1):
                s = compute_cut_score(words, k, k - start)
                if s > best_score:
                    best_score = s
                    best_cut = k
            cues.append((start, best_cut))
            start = best_cut
            i = start + 1
            continue

        # Below minimum
        if wsc < min_words:
            i += 1
            continue

        # Check if score crosses threshold
        score = compute_cut_score(words, i, wsc)
        if score >= threshold:
            cues.append((start, i))
            start = i
        i += 1

    if start < len(words):
        cues.append((start, len(words)))

    # Post-process: rebalance orphan tails within sentences
    cues = rebalance_orphans(cues, words)

    return cues


def rebalance_orphans(cues, words, min_tail=3, max_words=10):
    """If a cue has <3 words and ends before a sentence end, try to merge with prior
    cue if combined ≤ max_words."""
    if len(cues) < 2:
        return cues
    merged = [cues[0]]
    for s, e in cues[1:]:
        ps, pe = merged[-1]
        cue_len = e - s
        combined = e - ps
        prev_word = words[pe - 1]["word"] if pe > 0 else ""
        if cue_len < min_tail and combined <= max_words and not is_sent_end(prev_word):
            merged[-1] = (ps, e)
        else:
            merged.append((s, e))
    return merged


# -------- Output --------

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "editor.html"


def write_draft_txt(cues, words, output_path):
    lines = [
        "# Subtitle draft — one subtitle per non-empty, non-comment line",
        "# Comments (lines starting with #) are ignored by build_srt.py",
        "# You can edit freely: split lines, merge lines, adjust punctuation.",
        "# Try to avoid changing the actual words (the time-alignment uses word matching).",
        "",
    ]
    for n, (s, e) in enumerate(cues, 1):
        text = " ".join(words[i]["word"] for i in range(s, e))
        lines.append(f"{n:>3}  {text}")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_draft_html(cues, words, output_path, title):
    sample = [" ".join(words[i]["word"] for i in range(s, e)) for s, e in cues]
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()
    # safe JSON; the placeholder sits where the JS literal goes
    html = template.replace("__TITLE__", title)
    html = html.replace("__SAMPLE_JSON__", json.dumps(sample, ensure_ascii=False))
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_srt", nargs="?", help="Input raw SRT file")
    ap.add_argument("--timeline-in", help="Input timeline JSON (from transcribe.py, preferred)")
    ap.add_argument("--output", required=True, help="Output draft path (.html or .txt)")
    ap.add_argument("--timeline", required=True, help="Output timeline JSON (for build_srt.py)")
    ap.add_argument("--format", choices=["html", "txt"], default=None,
                    help="Force output format (default: inferred from --output extension; .html if unclear)")
    ap.add_argument("--title", default=None,
                    help="Title shown in the HTML editor (default: input filename stem)")
    ap.add_argument("--max-words", type=int, default=10, help="Max words per cue (hard cap)")
    ap.add_argument("--min-words", type=int, default=3, help="Min words per cue (except sentence ends)")
    ap.add_argument("--threshold", type=float, default=2.5, help="Score threshold for cutting")
    args = ap.parse_args()

    if args.timeline_in:
        with open(args.timeline_in, encoding="utf-8") as f:
            words = json.load(f)
    elif args.input_srt:
        entries = parse_srt(args.input_srt)
        words = srt_to_word_timeline(entries)
    else:
        sys.exit("Error: provide either an input SRT or --timeline-in JSON")

    # Normalize keys (accept both old and new timeline formats)
    for w in words:
        if "pause_after" not in w:
            w["pause_after"] = False

    # Heuristic: inject missing sentence boundaries
    words = inject_missing_sentence_boundaries(words)

    # Segment
    cues = segment(words, max_words=args.max_words, min_words=args.min_words, threshold=args.threshold)

    # Stats
    word_counts = [e - s for s, e in cues]
    hist = Counter(word_counts)
    print(f"Total words: {len(words)}")
    print(f"Total cues: {len(cues)}")
    print(f"Word distribution: {dict(sorted(hist.items()))}")
    print(f"Max words per cue: {max(word_counts)}")
    print(f"Avg words per cue: {sum(word_counts) / len(word_counts):.1f}")

    # Determine output format
    fmt = args.format
    if fmt is None:
        ext = Path(args.output).suffix.lower()
        fmt = "txt" if ext == ".txt" else "html"

    # Determine title for HTML editor
    title = args.title
    if title is None:
        source = args.input_srt or args.timeline_in or "Subtitle"
        title = Path(source).stem

    # Write outputs
    if fmt == "html":
        write_draft_html(cues, words, args.output, title)
    else:
        write_draft_txt(cues, words, args.output)
    with open(args.timeline, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=None)

    print(f"\nWrote draft ({fmt}): {args.output}")
    print(f"Wrote timeline: {args.timeline}")
    if fmt == "html":
        print(f"\nNext: run the self-review checklist silently, then open the HTML draft "
              f"in a browser for the user. When they click Finish and paste back, save the paste "
              f"to a .txt file and run build_srt.py.")
    else:
        print(f"\nNext: apply self-review checklist (see reference/), then run build_srt.py")


if __name__ == "__main__":
    main()
