import os
import json
import subprocess
import sys
from .video_downloader import download_video
from .video_normalizer import normalize_video
from .audio_extractor import extract_audio
from .asr_service import transcribe_with_default
from .highlight_engine import detect_highlights
from .video_cutter import group_segments_to_clips, cut_clips


def _write_srt(segments, out_srt_path):
    def fmt_ts(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, seg in enumerate(segments, start=1):
        start = fmt_ts(seg["start"]) if seg.get("start") is not None else "00:00:00,000"
        end = fmt_ts(seg["end"]) if seg.get("end") is not None else "00:00:00,000"
        text = seg.get("text", "")
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")

    os.makedirs(os.path.dirname(out_srt_path), exist_ok=True)
    with open(out_srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_full_pipeline(video_url: str, job_id: str):
    """Run a minimal demo pipeline synchronously:
    download -> normalize -> extract audio -> ASR -> write SRT + transcript json
    """
    base = os.getcwd()
    raw_path = os.path.join(base, "storage", "raw_videos", f"{job_id}.%(ext)s")
    # yt-dlp style output path expects a template; download_video will write exact file
    downloaded = os.path.join(base, "storage", "raw_videos", f"{job_id}.mp4")

    def _write_status(state: str, extra: dict = None):
        status_path = os.path.join(base, "storage", "transcripts", f"{job_id}_status.json")
        payload = {"video_id": job_id, "status": state}
        if extra:
            payload.update(extra)
        try:
            os.makedirs(os.path.dirname(status_path), exist_ok=True)
            with open(status_path, "w", encoding="utf-8") as sf:
                json.dump(payload, sf, ensure_ascii=False)
        except Exception:
            pass

    try:
        _write_status("downloading")
        download_video(video_url, downloaded)
        # try to extract a thumbnail frame
        try:
            thumb_dir = os.path.join(base, "storage", "transcripts")
            os.makedirs(thumb_dir, exist_ok=True)
            thumb_path = os.path.join(thumb_dir, f"{job_id}_thumbnail.jpg")
            # capture frame at 3 seconds
            subprocess.run(["ffmpeg", "-y", "-ss", "3", "-i", downloaded, "-frames:v", "1", "-q:v", "2", thumb_path], check=False)
            _write_status("downloaded", {"thumbnail": f"/storage/transcripts/{job_id}_thumbnail.jpg"})
        except Exception:
            _write_status("downloaded")
        normalized = os.path.join(base, "storage", "normalized", f"{job_id}.mp4")
        _write_status("normalizing")
        normalize_video(downloaded, normalized)
        _write_status("audio_extracting")
        audio_path = os.path.join(base, "storage", "audio", f"{job_id}.wav")
        extract_audio(normalized, audio_path)
        _write_status("transcribing")
        segments = []
        try:
            segments = transcribe_with_default(audio_path)
        except Exception as e:
            # ASR failed — write empty transcript metadata
            segments = [{"start": 0.0, "end": 0.0, "text": f"ASR error: {e}"}]
        _write_status("transcribed")
        subs_path = os.path.join(base, "storage", "subtitles", f"{job_id}.srt")
        _write_srt(segments, subs_path)

        # save transcript JSON
        transcript_path = os.path.join(base, "storage", "transcripts", f"{job_id}.json")
        os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)

        _write_status("detecting_highlights")
        # detect highlights (rule-based) and save
        try:
            highlights = detect_highlights(segments, audio_path)
        except Exception as e:
            highlights = [{"error": str(e)}]

        highlights_path = os.path.join(base, "storage", "transcripts", f"{job_id}_highlights.json")
        with open(highlights_path, "w", encoding="utf-8") as f:
            json.dump(highlights, f, ensure_ascii=False, indent=2)

        _write_status("generating_clips")
        # auto-generate clips by grouping transcript segments
        try:
            clips_specs = group_segments_to_clips(segments, min_len=15, max_len=60, gap_threshold=3.0)
            clips_dir = os.path.join(base, "storage", "clips", job_id)
            os.makedirs(clips_dir, exist_ok=True)
            cut_files = cut_clips(normalized, clips_specs, clips_dir)

            # For each cut file, create per-clip SRT, burn subtitles, and create vertical format
            from .subtitle_burner import write_clip_srt, burn_subtitles
            from .video_formatter import format_vertical

            final_dir = os.path.join(base, "storage", "final_clips", job_id)
            os.makedirs(final_dir, exist_ok=True)

            final_meta = []
            for idx, cf in enumerate(cut_files, start=1):
                clip_file = cf.get("file")
                clip_start = cf.get("start", 0.0)
                clip_end = cf.get("end", clip_start + cf.get("duration", 0.0))
                # per-clip srt
                clip_srt = os.path.join(base, "storage", "subtitles", f"{job_id}_clip_{idx:02d}.srt")
                write_clip_srt(segments, clip_start, clip_end, clip_srt)

                # burned subtitles file
                burned = os.path.join(final_dir, f"clip_{idx:02d}_burned.mp4")
                try:
                    burn_subtitles(clip_file, clip_srt, burned)
                except Exception:
                    # fallback: copy clip as burned (no subtitles)
                    burned = clip_file

                # vertical formatted
                vertical = os.path.join(final_dir, f"clip_{idx:02d}_vertical.mp4")
                try:
                    format_vertical(burned, vertical)
                except Exception:
                    # fallback to burned if formatting fails
                    vertical = burned

                final_meta.append({"clip": cf, "burned": burned, "vertical": vertical})

            clips_meta_path = os.path.join(base, "storage", "transcripts", f"{job_id}_clips.json")
            with open(clips_meta_path, "w", encoding="utf-8") as f:
                json.dump(final_meta, f, ensure_ascii=False, indent=2)
            _write_status("finished", {"clips_count": len(final_meta)})
        except Exception as e:
            clips_meta_path = os.path.join(base, "storage", "transcripts", f"{job_id}_clips_error.log")
            with open(clips_meta_path, "w", encoding="utf-8") as f:
                f.write(str(e))
            _write_status("error", {"error": str(e)})

    except Exception as e:
        # basic logging to a file
        log_path = os.path.join(base, "storage", "transcripts", f"{job_id}_error.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(str(e))
        try:
            _write_status("error", {"error": str(e)})
        except Exception:
            pass
