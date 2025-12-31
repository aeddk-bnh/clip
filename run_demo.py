import sys
import uuid

sys.path.insert(0, "backend")

from app.services.pipeline import run_full_pipeline


def main():
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
    job_id = str(uuid.uuid4())
    print("Starting pipeline for", url)
    run_full_pipeline(url, job_id)
    print("Finished pipeline. job_id=", job_id)


if __name__ == "__main__":
    main()
