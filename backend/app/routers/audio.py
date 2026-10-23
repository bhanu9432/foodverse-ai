"""Objective 8 (audio): speech-to-text so users can speak a food note or a cooking question.
Uses faster-whisper when installed (pip install -r requirements-audio.txt)."""
import os
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import config, media

router = APIRouter(prefix="/api/audio", tags=["audio"])
_model = None


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def transcribe_file(path: str) -> str:
    segments, _info = _get_model().transcribe(path, vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    if not available():
        raise HTTPException(501, "Server speech-to-text is not installed. Run: pip install -r requirements-audio.txt")
    data = await media.read_limited(audio, config.MAX_AUDIO_BYTES, "Audio")
    suffix = os.path.splitext(audio.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        text = transcribe_file(path)
    except Exception:
        raise HTTPException(400, "That audio could not be transcribed.")
    finally:
        os.unlink(path)
    if not text:
        raise HTTPException(422, "No speech was detected. Try again closer to the microphone.")
    return {"text": text}
