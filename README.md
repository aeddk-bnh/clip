# AI Auto Short Clip - Demo (scaffold)

This workspace contains a minimal FastAPI demo pipeline for converting a video URL into transcript and SRT.

Prerequisites
- Install system `ffmpeg` and make sure it's on PATH.
- Python 3.10+ and virtualenv.

Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt

# run server
uvicorn app.main:app --reload --port 8000
```

Then POST JSON to `http://localhost:8000/process-by-url`:

```json
{
  "video_url": "https://www.youtube.com/watch?v=...",
  "platform": "auto"
}
```

Notes
- The demo uses `yt-dlp` and `ffmpeg` via subprocess — both must be available on the system.
- `faster-whisper` is used for ASR; CPU mode will be slow. For decent performance install appropriate CUDA/cuDNN and a GPU build.
