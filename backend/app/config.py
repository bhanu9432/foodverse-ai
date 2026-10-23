"""Settings read from environment variables (and an optional .env file)."""
import os
from pathlib import Path


def _load_dotenv() -> None:
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("FOODVERSE_MODEL", "claude-sonnet-5-5")
DB_PATH = os.getenv("FOODVERSE_DB", "foodverse.db")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_VIDEO_BYTES = 60 * 1024 * 1024
MAX_AUDIO_BYTES = 15 * 1024 * 1024
MAX_IMAGE_SIDE = 1568  # longest side sent to the model
VIDEO_FRAMES = 8       # frames sampled from a kitchen video
