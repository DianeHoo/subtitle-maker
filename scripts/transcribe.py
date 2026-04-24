#!/usr/bin/env python3
"""Transcribe a video/audio file to SRT with word-level timestamps.

Prefers WhisperX (forced alignment, precise word timings). Falls back to
vanilla Whisper with linear interpolation if WhisperX unavailable.

Usage:
    python transcribe.py input.mp4 --output out.srt --timeline timeline.json
    python transcribe.py input.mov --model large-v3 --language en

Output:
    - SRT file with segment-level cues (raw, uncleaned)
    - Timeline JSON: [{"word": "...", "start_ms": N, "end_ms": N, "pause_after": bool}, ...]
      The pause_after field marks original ASR cue boundaries — used by segment.py
      to respect speaker breath points.
"""
import argparse
import json
import sys
from pathlib import Path


def ms_to_srt(ms: int) -> str:
    ms = max(0, int(round(ms)))
    h = ms // 3600000; ms -= h * 3600000
    m = ms // 60000; ms -= m * 60000
    s = ms // 1000; ms -= s * 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def try_whisperx(input_path: str, model_size: str, language: str):
    """Return (segments_with_words, pause_markers) or None if WhisperX unavailable."""
    try:
        import whisperx
        import torch
    except ImportError:
        return None

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"

    model = whisperx.load_model(model_size, device, compute_type=compute_type, language=language)
    audio = whisperx.load_audio(input_path)
    result = model.transcribe(audio, batch_size=16)

    align_model, metadata = whisperx.load_align_model(language_code=language, device=device)
    aligned = whisperx.align(
        result["segments"], align_model, metadata, audio, device, return_char_alignments=False
    )
    return aligned["segments"], "whisperx"


def try_whisper(input_path: str, model_size: str, language: str):
    """Fallback: vanilla Whisper with word-level timestamps (slower but more widely installed)."""
    try:
        import whisper
    except ImportError:
        return None

    model = whisper.load_model(model_size)
    result = model.transcribe(input_path, language=language, word_timestamps=True)
    return result["segments"], "whisper"


def build_word_timeline(segments, backend: str):
    """Flatten segments into a word-level timeline with pause_after flags."""
    words = []
    for seg_idx, seg in enumerate(segments):
        is_last_seg = seg_idx == len(segments) - 1
        if backend == "whisperx" or backend == "whisper":
            seg_words = seg.get("words", [])
            if not seg_words:
                # Interpolate from segment-level timestamps
                text = seg["text"].strip()
                tokens = text.split()
                if not tokens:
                    continue
                seg_start = seg["start"] * 1000
                seg_end = seg["end"] * 1000
                step = (seg_end - seg_start) / len(tokens)
                for i, tok in enumerate(tokens):
                    pause_after = (i == len(tokens) - 1 and not is_last_seg)
                    words.append({
                        "word": tok,
                        "start_ms": int(seg_start + i * step),
                        "end_ms": int(seg_start + (i + 1) * step),
                        "pause_after": pause_after,
                    })
            else:
                for i, w in enumerate(seg_words):
                    word_text = w.get("word", w.get("text", "")).strip()
                    if not word_text:
                        continue
                    start = w.get("start", seg["start"]) * 1000
                    end = w.get("end", seg["end"]) * 1000
                    pause_after = (i == len(seg_words) - 1 and not is_last_seg)
                    words.append({
                        "word": word_text,
                        "start_ms": int(start),
                        "end_ms": int(end),
                        "pause_after": pause_after,
                    })
    return words


def write_srt_from_segments(segments, output_path: str):
    """Write raw segment-level SRT."""
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = int(seg["start"] * 1000)
            end = int(seg["end"] * 1000)
            text = seg["text"].strip()
            f.write(f"{i}\n{ms_to_srt(start)} --> {ms_to_srt(end)}\n{text}\n\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="Video/audio file path")
    ap.add_argument("--output", default=None, help="Output SRT path (default: <input>.srt)")
    ap.add_argument("--timeline", default=None, help="Output timeline JSON (default: <input>_timeline.json)")
    ap.add_argument("--model", default="large-v3", help="Whisper model size (tiny/base/small/medium/large-v3)")
    ap.add_argument("--language", default="en", help="Language code (en, zh, es, ...)")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"Error: input file {input_path} does not exist")

    output_path = args.output or str(input_path.with_suffix(".srt"))
    timeline_path = args.timeline or str(input_path.with_name(input_path.stem + "_timeline.json"))

    print(f"Transcribing {input_path.name} with model={args.model} language={args.language}...")

    result = try_whisperx(str(input_path), args.model, args.language)
    if result is None:
        print("WhisperX not available, falling back to vanilla Whisper...")
        result = try_whisper(str(input_path), args.model, args.language)
    if result is None:
        sys.exit("Error: neither whisperx nor whisper is installed. "
                 "Install: pip install whisperx   (preferred)   OR   pip install openai-whisper")

    segments, backend = result
    print(f"Using backend: {backend}, got {len(segments)} segments")

    words = build_word_timeline(segments, backend)
    print(f"Extracted {len(words)} words with timestamps")

    write_srt_from_segments(segments, output_path)
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=None)

    print(f"Wrote SRT: {output_path}")
    print(f"Wrote timeline: {timeline_path}")


if __name__ == "__main__":
    main()
