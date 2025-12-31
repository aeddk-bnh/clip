import os
import subprocess
from imageio_ffmpeg import get_ffmpeg_exe


def format_vertical(input_video: str, out_video: str, width: int = 1080, height: int = 1920):
    """Format `input_video` to vertical 9:16 (width x height) by scaling and center cropping/padding.

    Uses an ffmpeg filter chain to scale to target height, crop center to width:height,
    and pad if necessary to exactly match dimensions.
    """
    os.makedirs(os.path.dirname(out_video), exist_ok=True)

    vf = (
        "scale='if(gt(a,9/16),-1,{} )':'if(gt(a,9/16),{},-1)',"
        "crop={}:{}", 
    ).format(width, height, width, height)

    # Add pad to ensure exact size (centering)
    vf = f"scale='if(gt(a,9/16),-1,{height})':'if(gt(a,9/16),{height},-1)',crop={width}:{height},pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"

    ffmpeg = get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        input_video,
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-c:a",
        "aac",
        out_video,
    ]
    subprocess.check_call(cmd)
