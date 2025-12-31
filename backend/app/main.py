from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
import threading
from pydantic import BaseModel
import uuid
import os
import json

from .services.pipeline import run_full_pipeline


app = FastAPI(title="AI Auto Short Clip - Demo")


class ProcessRequest(BaseModel):
    video_url: str
    platform: str = "auto"


@app.post("/process-by-url")
async def process_by_url(req: ProcessRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    # ensure storage folders exist
    os.makedirs("storage/raw_videos", exist_ok=True)
    os.makedirs("storage/normalized", exist_ok=True)
    os.makedirs("storage/audio", exist_ok=True)
    os.makedirs("storage/subtitles", exist_ok=True)
    os.makedirs("storage/transcripts", exist_ok=True)
    os.makedirs("storage/final_clips", exist_ok=True)

    # run the long-running pipeline in a separate daemon thread to avoid
    # blocking the uvicorn worker or causing unexpected shutdowns
    def _start():
        try:
            run_full_pipeline(req.video_url, job_id)
        except Exception:
            # don't let exceptions in pipeline crash the web process
            import traceback
            traceback.print_exc()

    background_tasks.add_task(lambda: threading.Thread(target=_start, daemon=True).start())
    return {"video_id": job_id, "status": "queued"}


@app.get("/health")
def health():
    return {"status": "ok"}


# serve frontend static files under /static and expose index at /
app.mount("/static", StaticFiles(directory="frontend"), name="static")
@app.get("/")
def index():
    index_path = os.path.join("frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return JSONResponse({"message": "UI not found; open /static/index.html"})
# serve storage for downloads / final clips
app.mount("/storage", StaticFiles(directory="storage"), name="storage")


@app.get("/status/{video_id}")
def get_status(video_id: str):
    status_path = os.path.join("storage", "transcripts", f"{video_id}_status.json")
    if not os.path.exists(status_path):
        return JSONResponse({"video_id": video_id, "status": "queued"})
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/clips/{video_id}")
def list_clips(video_id: str):
    # read clips metadata produced by pipeline
    clips_meta = os.path.join("storage", "transcripts", f"{video_id}_clips.json")
    final_dir = os.path.join("storage", "final_clips", video_id)
    if not os.path.exists(final_dir):
        return JSONResponse({"video_id": video_id, "clips": []})
    clips = []
    # try to read metadata
    if os.path.exists(clips_meta):
        try:
            with open(clips_meta, "r", encoding="utf-8") as f:
                meta = json.load(f)
            for i, m in enumerate(meta, start=1):
                vertical = m.get("vertical")
                burned = m.get("burned")
                filename = None
                if vertical and os.path.exists(vertical):
                    filename = os.path.relpath(vertical, "storage")
                elif burned and os.path.exists(burned):
                    filename = os.path.relpath(burned, "storage")
                else:
                    files = os.listdir(final_dir)
                    if files:
                        filename = os.path.join(video_id, files[0])
                if filename:
                    clips.append({"id": i, "url": f"/storage/{filename.replace('\\', '/')}", "meta": m.get("clip", {})})
        except Exception:
            pass
    else:
        for fname in sorted(os.listdir(final_dir)):
            clips.append({"id": fname, "url": f"/storage/final_clips/{video_id}/{fname}"})

    return JSONResponse({"video_id": video_id, "clips": clips})
