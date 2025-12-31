import os
import subprocess
from typing import List, Dict


def group_segments_to_clips(segments: List[Dict], min_len: int = 15, max_len: int = 60, gap_threshold: float = 3.0) -> List[Dict]:
    """Group transcript segments into clip ranges.

    Algorithm (simple greedy):
    - sort segments by start
    - accumulate adjacent segments when gap <= gap_threshold and total length <= max_len
    - if accumulated length < min_len, extend end to start+min_len (bounded by max_len)
    Returns list of {'start': float, 'end': float}
    """
    if not segments:
        return []

    segs = sorted(segments, key=lambda s: float(s.get("start", 0.0)))
    clips = []
    cur_start = float(segs[0].get("start", 0.0))
    cur_end = float(segs[0].get("end", cur_start))

    for s in segs[1:]:
        s_start = float(s.get("start", 0.0))
        s_end = float(s.get("end", s_start))
        gap = s_start - cur_end
        potential_end = s_end
        combined_len = potential_end - cur_start

        if gap <= gap_threshold and combined_len <= max_len:
            # merge into current clip
            cur_end = max(cur_end, s_end)
            # if merged length exceeds max_len, cap
            if (cur_end - cur_start) > max_len:
                cur_end = cur_start + max_len
                clips.append({"start": cur_start, "end": cur_end})
                # start a new clip from this segment's remaining portion
                cur_start = cur_end
                cur_end = cur_end
        else:
            # finalize current clip (ensure min_len)
            length = cur_end - cur_start
            if length < min_len:
                cur_end = min(cur_start + min_len, cur_start + max_len)
            clips.append({"start": cur_start, "end": cur_end})
            cur_start = s_start
            cur_end = s_end

    # finalize last
    length = cur_end - cur_start
    if length < min_len:
        cur_end = min(cur_start + min_len, cur_start + max_len)
    clips.append({"start": cur_start, "end": cur_end})

    # normalize floats
    for c in clips:
        c["start"] = float(c["start"]) if c.get("start") is not None else 0.0
        c["end"] = float(c["end"]) if c.get("end") is not None else c.get("start", 0.0)
    return clips


def cut_clips(input_video: str, clips: List[Dict], out_dir: str) -> List[Dict]:
    """Cut clips from `input_video` using ffmpeg and save to `out_dir`.

    Returns list of metadata dicts with keys: file, start, end, duration
    """
    os.makedirs(out_dir, exist_ok=True)
    out_files = []
    from imageio_ffmpeg import get_ffmpeg_exe
    ffmpeg = get_ffmpeg_exe()
    for idx, c in enumerate(clips, start=1):
        start = float(c.get("start", 0.0))
        end = float(c.get("end", start))
        duration = max(0.01, end - start)
        out_path = os.path.join(out_dir, f"clip_{idx:02d}.mp4")
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            input_video,
            "-ss",
            str(start),
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-c:a",
            "aac",
            out_path,
        ]
        subprocess.check_call(cmd)
        out_files.append({"file": out_path, "start": start, "end": end, "duration": duration})
    return out_files
