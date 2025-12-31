import os
import sys
from fastapi.testclient import TestClient

# ensure repo root is on sys.path
sys.path.append(os.getcwd())

from backend.app.main import app

client = TestClient(app)

resp = client.post("/process-by-url", json={"video_url": "https://www.youtube.com/watch?v=ttgAy7Z630Q"})
print('status_code=', resp.status_code)
print(resp.json())