import wave
import os
from typing import List, Dict

try:
    import audioop
    _HAS_AUDIOOP = True
except Exception:
    _HAS_AUDIOOP = False
    import numpy as _np

# Rule weights (tunable)
W_LENGTH = 0.4
W_KEYWORD = 0.3
W_ENERGY = 0.2
W_PAUSE = 0.1


def _segment_energy(wav_path: str, start_s: float, end_s: float) -> float:
    try:
        with wave.open(wav_path, "rb") as wf:
            framerate = wf.getframerate()
            sampwidth = wf.getsampwidth()
            start_frame = int(start_s * framerate)
            end_frame = int(end_s * framerate)
            num_frames = end_frame - start_frame
            if num_frames <= 0:
                return 0.0
            wf.setpos(start_frame)
            raw = wf.readframes(num_frames)
            if _HAS_AUDIOOP:
                rms = audioop.rms(raw, sampwidth)
            else:
                # fallback using numpy
                if sampwidth == 2:
                    dtype = _np.int16
                elif sampwidth == 4:
                    dtype = _np.int32
                else:
                    # unsupported sampwidth for fallback
                    return 0.0
                arr = _np.frombuffer(raw, dtype=dtype)
                if arr.size == 0:
                    return 0.0
                rms = float((_np.mean(arr.astype(_np.float64) ** 2)) ** 0.5)
            # normalize by maximum for signed PCM
            max_possible = float((2 ** (8 * sampwidth - 1)) - 1)
            return float(rms) / max_possible if max_possible > 0 else 0.0
    except Exception:
        return 0.0


def detect_highlights(segments: List[Dict], wav_path: str, keywords: List[str] = None, top_k: int = 5) -> List[Dict]:
    """Score segments and return top_k highlights.

    segments: list of {start, end, text}
    wav_path: path to mono WAV (16kHz) used to compute energy
    """
    if keywords is None:
        keywords = ["important", "key", "note", "best", "tip", "announc", "highlight"]

    scored = []
    # precompute gaps
    for i, seg in enumerate(segments):
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        length = max(0.0, end - start)

        # keyword presence
        text = (seg.get("text") or "").lower()
        kw_score = 1.0 if any(k in text for k in keywords) else 0.0

        # energy from audio
        energy = _segment_energy(wav_path, start, end) if os.path.exists(wav_path) else 0.0

        # pause before/after
        gap_before = 0.0
        gap_after = 0.0
        if i > 0:
            gap_before = max(0.0, start - float(segments[i - 1].get("end", start)))
        if i < len(segments) - 1:
            gap_after = max(0.0, float(segments[i + 1].get("start", end)) - end)
        pause_score = min(1.0, max(gap_before, gap_after) / 3.0)

        # normalized length factor (capped at 1 for >=30s)
        length_score = min(1.0, length / 30.0)

        score = W_LENGTH * length_score + W_KEYWORD * kw_score + W_ENERGY * energy + W_PAUSE * pause_score

        scored.append({
            "start": start,
            "end": end,
            "text": seg.get("text", ""),
            "length": length,
            "kw": kw_score,
            "energy": energy,
            "pause": pause_score,
            "score": score,
        })

    # sort by score desc
    scored_sorted = sorted(scored, key=lambda x: x["score"], reverse=True)
    return scored_sorted[:top_k]
