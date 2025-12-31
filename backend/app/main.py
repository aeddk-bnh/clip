from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import uuid
import os

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

    background_tasks.add_task(run_full_pipeline, req.video_url, job_id)
    return {"video_id": job_id, "status": "queued"}
