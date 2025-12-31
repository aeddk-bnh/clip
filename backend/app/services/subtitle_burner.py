import os
import subprocess
from typing import List, Dict
from imageio_ffmpeg import get_ffmpeg_exe


def _fmt_ts(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_clip_srt(segments: List[Dict], clip_start: float, clip_end: float, out_srt: str):
    """Write an SRT file containing only subtitle segments that overlap the clip.
    Times are shifted so clip_start => 0.
    """
    lines = []
    idx = 1
    for seg in segments:
        s = float(seg.get("start", 0.0))
        e = float(seg.get("end", s))
        # check overlap
        if e <= clip_start or s >= clip_end:
            continue
        # clipped times
        s2 = max(0.0, s - clip_start)
        e2 = min(clip_end - clip_start, e - clip_start)
        lines.append(str(idx))
        lines.append(f"{_fmt_ts(s2)} --> {_fmt_ts(e2)}")
        lines.append(seg.get("text", ""))
        lines.append("")
        idx += 1

    os.makedirs(os.path.dirname(out_srt), exist_ok=True)
    with open(out_srt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def burn_subtitles(input_video: str, srt_path: str, out_video: str):
    """Burn subtitles from `srt_path` into `input_video` using ffmpeg subtitles filter."""
    os.makedirs(os.path.dirname(out_video), exist_ok=True)
    # ffmpeg subtitles filter expects path; ensure proper escaping if needed
    ffmpeg = get_ffmpeg_exe()
    # Use the absolute path wrapped in single quotes so ffmpeg's subtitles
    # filter receives the correct filename (avoids parser issues on Windows).
    abs_srt = os.path.abspath(srt_path)
    clip_dir = os.path.dirname(os.path.abspath(input_video)) or "."
    # Copy SRT into the clip directory with a simple basename so ffmpeg's
    # libass can open it reliably on Windows when running from that folder.
    srt_basename = os.path.basename(abs_srt)
    local_srt = os.path.join(clip_dir, srt_basename)
    try:
        if os.path.abspath(abs_srt) != os.path.abspath(local_srt):
            with open(abs_srt, "rb") as src, open(local_srt, "wb") as dst:
                dst.write(src.read())
    except Exception:
        # If copying fails, fall back to using absolute path in the filter.
        local_srt = abs_srt

    vf_arg = f"subtitles={srt_basename if os.path.exists(local_srt) else local_srt}"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        input_video,
        "-vf",
        vf_arg,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-c:a",
        "aac",
        out_video,
    ]
    subprocess.check_call(cmd, cwd=clip_dir)
