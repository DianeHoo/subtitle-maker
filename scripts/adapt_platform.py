#!/usr/bin/env python3
"""Adapt an SRT file to a target platform's conventions.

Usage:
    python adapt_platform.py final.srt --target youtube --output final_youtube.srt
    python adapt_platform.py final.srt --target davinci
    python adapt_platform.py final.srt --target tiktok --max-words 5
    python adapt_platform.py final.srt --target webvtt --output final.vtt
    python adapt_platform.py final.srt --target broadcast --smpte-offset 01:00:00:00

Targets:
    youtube  -- strip styling tags, ensure 00:00:00 start, UTF-8
    davinci  -- preserve styling tags, ensure 00:00:00 start
    tiktok   -- strip tags + force shorter cues (requires re-segmentation upstream)
    instagram -- same as tiktok
    webvtt   -- convert to WebVTT format (.vtt)
    broadcast -- apply SMPTE offset (e.g., 01:00:00:00 preroll)
    generic  -- strip tags, UTF-8, 00:00:00 start — safest vanilla

See reference/platform_specs.md for details.
"""
import argparse
import re
import sys
from pathlib import Path


def parse_srt(path: str):
    with open(path, encoding="utf-8") as f:
        data = f.read()
    blocks = re.split(r"\n\s*\n", data.strip())
    out = []
    for b in blocks:
        lines = b.splitlines()
        if len(lines) < 3:
            continue
        idx = lines[0].strip()
        timing = lines[1].strip()
        text = "\n".join(lines[2:])
        out.append((idx, timing, text))
    return out


def srt_to_ms(ts: str):
    m = re.match(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", ts)
    if not m:
        raise ValueError(f"Bad timestamp: {ts}")
    h, mm, s, ms = map(int, m.groups())
    return h * 3600000 + mm * 60000 + s * 1000 + ms


def ms_to_srt(ms):
    ms = max(0, int(ms))
    h = ms // 3600000; ms -= h * 3600000
    m = ms // 60000; ms -= m * 60000
    s = ms // 1000; ms -= s * 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ms_to_vtt(ms):
    s = ms_to_srt(ms)
    return s.replace(",", ".")


def smpte_to_ms(smpte: str, fps: float = 24.0):
    m = re.match(r"(\d{2}):(\d{2}):(\d{2}):(\d{2})", smpte)
    if not m:
        raise ValueError(f"Bad SMPTE: {smpte}")
    h, mm, s, fr = map(int, m.groups())
    total_frames = fr + s * fps + mm * 60 * fps + h * 3600 * fps
    return int(total_frames * 1000 / fps)


def strip_style_tags(text: str) -> str:
    text = re.sub(r"</?b>", "", text)
    text = re.sub(r"</?i>", "", text)
    text = re.sub(r"</?u>", "", text)
    text = re.sub(r"<font[^>]*>", "", text)
    text = re.sub(r"</font>", "", text)
    return text


def apply_time_offset(cues, offset_ms: int):
    new = []
    for idx, timing, text in cues:
        m = re.match(
            r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})",
            timing,
        )
        if not m:
            new.append((idx, timing, text))
            continue
        s1 = srt_to_ms(m.group(1)) + offset_ms
        s2 = srt_to_ms(m.group(2)) + offset_ms
        new.append((idx, f"{ms_to_srt(s1)} --> {ms_to_srt(s2)}", text))
    return new


def write_srt(cues, path: str):
    with open(path, "w", encoding="utf-8") as f:
        for idx, timing, text in cues:
            f.write(f"{idx}\n{timing}\n{text}\n\n")


def write_vtt(cues, path: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for idx, timing, text in cues:
            m = re.match(
                r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})",
                timing,
            )
            if m:
                vtt_timing = f"{ms_to_vtt(srt_to_ms(m.group(1)))} --> {ms_to_vtt(srt_to_ms(m.group(2)))}"
            else:
                vtt_timing = timing.replace(",", ".")
            f.write(f"{idx}\n{vtt_timing}\n{text}\n\n")


def adapt(cues, target: str, smpte_offset: str = None, fps: float = 24.0):
    if target in ("youtube", "generic", "tiktok", "instagram", "webvtt"):
        cues = [(i, t, strip_style_tags(x)) for (i, t, x) in cues]
    if target == "broadcast" and smpte_offset:
        offset_ms = smpte_to_ms(smpte_offset, fps)
        cues = apply_time_offset(cues, offset_ms)
    return cues


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="Input SRT file")
    ap.add_argument("--target", required=True,
                    choices=["youtube", "davinci", "tiktok", "instagram", "webvtt", "broadcast", "generic"])
    ap.add_argument("--output", default=None, help="Output path (default: inferred from target)")
    ap.add_argument("--smpte-offset", default=None, help="SMPTE offset for broadcast (e.g., 01:00:00:00)")
    ap.add_argument("--fps", type=float, default=24.0, help="Frame rate (for broadcast SMPTE conversion)")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"Error: {input_path} does not exist")

    if args.output:
        output_path = Path(args.output)
    else:
        if args.target == "webvtt":
            output_path = input_path.with_suffix(".vtt")
        else:
            stem = input_path.stem
            output_path = input_path.with_name(f"{stem}_{args.target}.srt")

    cues = parse_srt(str(input_path))
    print(f"Read {len(cues)} cues from {input_path.name}")

    cues = adapt(cues, args.target, args.smpte_offset, args.fps)

    if args.target == "webvtt":
        write_vtt(cues, str(output_path))
    else:
        write_srt(cues, str(output_path))

    print(f"Wrote {args.target}-adapted file: {output_path}")

    if args.target in ("tiktok", "instagram"):
        print("\nNote: for true TikTok/IG style (2-5 word cues), re-run segment.py "
              "with --max-words 5 on the original draft first, then build_srt.py, then this.")


if __name__ == "__main__":
    main()
