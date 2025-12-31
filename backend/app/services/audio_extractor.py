import subprocess
import os
from imageio_ffmpeg import get_ffmpeg_exe


def extract_audio(video_path: str, out_wav: str, rate: int = 16000):
    """Extract audio as mono WAV with given sample rate using ffmpeg."""
    os.makedirs(os.path.dirname(out_wav), exist_ok=True)
    ffmpeg = get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        video_path,
        "-ar",
        str(rate),
        "-ac",
        "1",
        out_wav,
    ]
    subprocess.check_call(cmd)
