"""Image and video preparation: validate, downscale, and turn into model-ready base64."""
import base64
import io
import os
import tempfile

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps

from . import config

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime", "video/x-matroska", "video/x-msvideo"}


def _encode(img: Image.Image) -> str:
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((config.MAX_IMAGE_SIDE, config.MAX_IMAGE_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return base64.standard_b64encode(buf.getvalue()).decode()


async def read_limited(file: UploadFile, limit: int, what: str) -> bytes:
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"{what} is larger than {limit // (1024 * 1024)} MB.")
    if not data:
        raise HTTPException(400, f"{what} is empty.")
    return data


async def image_to_b64(file: UploadFile) -> str:
    if (file.content_type or "").lower() not in IMAGE_TYPES:
        raise HTTPException(415, "Please upload a JPEG, PNG, WebP or GIF image.")
    data = await read_limited(file, config.MAX_IMAGE_BYTES, "Image")
    try:
        return _encode(Image.open(io.BytesIO(data)))
    except Exception:
        raise HTTPException(400, "That file could not be read as an image.")


def sample_frames(video_path: str, n: int | None = None) -> list[str]:
    """Return up to n evenly spaced frames as base64 JPEG strings."""
    n = n or config.VIDEO_FRAMES
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(400, "That file could not be opened as a video.")
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        idxs = sorted({int(i * (total - 1) / max(1, n - 1)) for i in range(n)}) if total > 0 else []
        frames: list[str] = []
        if idxs:
            for i in idxs:
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ok, frame = cap.read()
                if ok:
                    frames.append(_encode(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))))
        if not frames:  # some containers do not report frame counts: read sequentially
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            allf = []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                allf.append(frame)
                if len(allf) > 1500:
                    break
            if allf:
                pick = np.linspace(0, len(allf) - 1, min(n, len(allf))).astype(int)
                frames = [_encode(Image.fromarray(cv2.cvtColor(allf[i], cv2.COLOR_BGR2RGB))) for i in pick]
        if not frames:
            raise HTTPException(400, "No frames could be read from that video.")
        return frames
    finally:
        cap.release()


async def video_to_frames(file: UploadFile) -> list[str]:
    if (file.content_type or "").lower() not in VIDEO_TYPES:
        raise HTTPException(415, "Please upload an MP4, WebM or MOV video.")
    data = await read_limited(file, config.MAX_VIDEO_BYTES, "Video")
    suffix = os.path.splitext(file.filename or "")[1] or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        return sample_frames(path)
    finally:
        os.unlink(path)
