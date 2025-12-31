import subprocess
import os
import sys


def download_video(url: str, out_path: str):
    """Download video using yt-dlp invoked with the same Python interpreter.

    This calls `python -m yt_dlp` so it works even when `yt-dlp` is not on PATH
    but installed in the same virtualenv.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cmd = [sys.executable, "-m", "yt_dlp", "-f", "best", "-o", out_path, url]
    subprocess.check_call(cmd)
