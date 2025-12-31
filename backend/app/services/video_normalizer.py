import subprocess
import os
from imageio_ffmpeg import get_ffmpeg_exe


def normalize_video(in_path: str, out_path: str, fps: int = 30):
    """Normalize video to H.264, given fps. Uses imageio-ffmpeg's binary if system ffmpeg missing."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    ffmpeg = get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        in_path,
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        out_path,
    ]
    subprocess.check_call(cmd)
