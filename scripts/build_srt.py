#!/usr/bin/env python3
"""Build a final SRT from an edited draft + word-level timeline.

Each non-empty, non-comment line in the draft becomes one SRT cue. Words in the
draft are aligned against the timeline via SequenceMatcher; words the user added
or changed get timestamps interpolated from neighboring matched words.

Usage:
    python build_srt.py draft.txt --timeline timeline.json --output final.srt

Optional:
    --style bold_black   Wrap each cue in <b><font color='#000000'>...</font></b>
                         (useful for DaVinci). Default: no styling.
    --min-duration 1000  Minimum cue duration in ms (default: 500)
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path


def norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def fmt_ms(ms) -> str:
    ms = max(0, int(round(ms)))
    h = ms // 3600000; ms -= h * 3600000
    m = ms // 60000; ms -= m * 60000
    s = ms // 1000; ms -= s * 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def read_draft_lines(path: str):
    """Return list of (line_text,) — one per non-empty non-comment line, leading number prefix stripped."""
    out = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            m = re.match(r"^\s*\d+\s+(.*)$", line)
            text = m.group(1).strip() if m else stripped
            if text:
                out.append(text)
    return out


def align_words_to_timeline(flat_words, timeline):
    """Use SequenceMatcher to find matches between draft words and timeline words.
    Returns list same length as flat_words, each element = index into timeline or None."""
    tl_norm = [norm(t["word"]) for t in timeline]
    dr_norm = [norm(w) for w in flat_words]
    sm = difflib.SequenceMatcher(a=tl_norm, b=dr_norm, autojunk=False)
    dr_to_tl = [None] * len(dr_norm)
    for block in sm.get_matching_blocks():
        for i in range(block.size):
            dr_to_tl[block.b + i] = block.a + i
    return dr_to_tl


def fill_interp(arr):
    """Fill None values with linear interpolation between nearest non-None neighbors."""
    n = len(arr)
    for i in range(n):
        if arr[i] is None:
            prev_i = i - 1
            while prev_i >= 0 and arr[prev_i] is None:
                prev_i -= 1
            next_i = i + 1
            while next_i < n and arr[next_i] is None:
                next_i += 1
            if prev_i >= 0 and next_i < n:
                arr[i] = arr[prev_i] + (arr[next_i] - arr[prev_i]) * (i - prev_i) / (next_i - prev_i)
            elif prev_i >= 0:
                arr[i] = arr[prev_i]
            elif next_i < n:
                arr[i] = arr[next_i]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft", help="Edited draft file (from segment.py, possibly user-edited)")
    ap.add_argument("--timeline", required=True, help="Timeline JSON (from segment.py)")
    ap.add_argument("--output", required=True, help="Output SRT path")
    ap.add_argument("--style", choices=["none", "bold_black"], default="none",
                    help="Styling to wrap cue text")
    ap.add_argument("--min-duration", type=int, default=500, help="Min cue duration in ms")
    args = ap.parse_args()

    with open(args.timeline, encoding="utf-8") as f:
        timeline = json.load(f)

    draft_lines = read_draft_lines(args.draft)
    if not draft_lines:
        sys.exit("Error: no usable lines found in draft")

    line_words = [ln.split() for ln in draft_lines]
    flat_words = [w for ws in line_words for w in ws]

    dr_to_tl = align_words_to_timeline(flat_words, timeline)
    matched = sum(1 for x in dr_to_tl if x is not None)
    print(f"Draft words: {len(flat_words)}, Timeline words: {len(timeline)}, Matched: {matched}")

    dr_start = [None] * len(flat_words)
    dr_end = [None] * len(flat_words)
    for i in range(len(flat_words)):
        if dr_to_tl[i] is not None:
            e = timeline[dr_to_tl[i]]
            dr_start[i] = e["start_ms"]
            dr_end[i] = e["end_ms"]
    fill_interp(dr_start)
    fill_interp(dr_end)

    # Per-line cue timing
    cues = []
    idx = 0
    for ws in line_words:
        s = dr_start[idx]
        e = dr_end[idx + len(ws) - 1]
        if e <= s:
            e = s + args.min_duration
        if e - s < args.min_duration:
            e = s + args.min_duration
        cues.append([s, e])
        idx += len(ws)

    # Fix overlaps
    for i in range(1, len(cues)):
        if cues[i][0] < cues[i - 1][1]:
            if cues[i][0] - cues[i - 1][0] >= args.min_duration:
                cues[i - 1][1] = cues[i][0]
            else:
                cues[i][0] = cues[i - 1][1]
                if cues[i][1] <= cues[i][0]:
                    cues[i][1] = cues[i][0] + args.min_duration

    # Emit
    blocks = []
    for n, (ws, (s, e)) in enumerate(zip(line_words, cues), 1):
        text = " ".join(ws)
        if args.style == "bold_black":
            text = f"<b><font color='#000000'>{text}</font></b>"
        blocks.append(f"{n}\n{fmt_ms(s)} --> {fmt_ms(e)}\n{text}")

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n\n".join(blocks) + "\n")

    durations = [c[1] - c[0] for c in cues]
    word_counts = [len(ws) for ws in line_words]
    print(f"\nOutput: {args.output}")
    print(f"Total cues: {len(cues)}")
    print(f"First cue start: {fmt_ms(cues[0][0])}")
    print(f"Last cue end:    {fmt_ms(cues[-1][1])}")
    print(f"Cue duration (ms): min={min(durations)}, max={max(durations)}, avg={sum(durations)//len(durations)}")
    print(f"Words per cue:   min={min(word_counts)}, max={max(word_counts)}, avg={sum(word_counts)/len(word_counts):.1f}")

    unmatched = [(i, flat_words[i]) for i in range(len(flat_words)) if dr_to_tl[i] is None]
    if unmatched:
        print(f"\nUnmatched words ({len(unmatched)}) — user edits, timestamps interpolated:")
        for i, w in unmatched[:20]:
            print(f"  [{i}] {w!r}")
        if len(unmatched) > 20:
            print(f"  ... and {len(unmatched) - 20} more")


if __name__ == "__main__":
    main()
