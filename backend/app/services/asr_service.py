from typing import List, Dict
import os

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None


class ASRService:
    def __init__(self, model_name: str = "small", device: str = "cpu"):
        if WhisperModel is None:
            raise RuntimeError("faster_whisper is not available. Install faster-whisper to use ASR.")
        self.model = WhisperModel(model_name, device=device)

    def transcribe(self, audio_path: str) -> List[Dict]:
        """Transcribe audio and return list of segments with start/end/text.

        Uses faster-whisper's `transcribe` which returns (segments, info).
        """
        segments, _ = self.model.transcribe(audio_path)
        # segments is an iterable of objects/dicts depending on model version
        out = []
        for s in segments:
            # support both dataclass-like and dict-like structures
            if hasattr(s, "start"):
                start = s.start
            else:
                start = s.get("start")

            if hasattr(s, "end"):
                end = s.end
            else:
                end = s.get("end")

            if hasattr(s, "text"):
                text = s.text
            else:
                text = s.get("text")

            # normalize values and guard against None
            try:
                start_f = float(start) if start is not None else 0.0
            except Exception:
                start_f = 0.0
            try:
                end_f = float(end) if end is not None else start_f
            except Exception:
                end_f = start_f

            text_str = (text or "").strip()
            out.append({"start": start_f, "end": end_f, "text": text_str})
        return out


def transcribe_with_default(audio_path: str):
    svc = ASRService()
    return svc.transcribe(audio_path)
