"""Objective 5: analyse kitchen video (or photos) for hygiene indicators."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import db, llm, media, scoring
from ..util import as_list, text

router = APIRouter(prefix="/api/hygiene", tags=["hygiene"])

_KEYS = ", ".join(f'"{k}" ({label})' for k, label, _ in scoring.HYGIENE_INDICATORS)

SYSTEM = f"""You are a food-safety auditor reviewing frames sampled in order from a kitchen video.
For each indicator decide: "compliant", "violation", or "not_visible" (you cannot tell from the frames).
Only report "violation" when you can actually see it. Never guess about people or things that are out of frame.
Indicators: {_KEYS}.
For each indicator give short evidence (what you saw) and the 1-based frame numbers where you saw it.
Do not identify or describe any person beyond what they are wearing and doing.
JSON shape:
{{"indicators": [{{"key": str, "status": "compliant"|"violation"|"not_visible", "evidence": str, "frames": [int]}}], \
"summary": str, "recommendations": [str]}}
Include every indicator key exactly once. "summary" is two sentences at most. Give at most 5 recommendations, \
most important first."""


def _validate(obj: dict, n_frames: int) -> dict:
    by_key = {}
    for ind in as_list(obj.get("indicators")):
        if isinstance(ind, dict) and ind.get("key") in {k for k, _, _ in scoring.HYGIENE_INDICATORS}:
            status = ind.get("status")
            if status not in scoring.HYGIENE_STATUSES:
                raise ValueError(f"bad status for {ind.get('key')}")
            frames = [int(f) for f in as_list(ind.get("frames")) if str(f).isdigit() and 1 <= int(f) <= n_frames]
            by_key[ind["key"]] = {"status": status, "evidence": text(ind.get("evidence"), 240), "frames": frames}
    out = []
    for key, label, weight in scoring.HYGIENE_INDICATORS:
        got = by_key.get(key, {"status": "not_visible", "evidence": "", "frames": []})
        out.append({"key": key, "label": label, "weight": weight, **got})
    return {
        "indicators": out,
        "summary": text(obj.get("summary"), 500),
        "recommendations": [text(r, 200) for r in as_list(obj.get("recommendations"))[:5] if r],
    }


@router.post("/analyze")
async def analyze(
    video: UploadFile | None = File(None),
    images: list[UploadFile] = File(default_factory=list),
    note: str = Form(""),
):
    frames: list[str] = []
    if video is not None:
        frames = await media.video_to_frames(video)
    for img in images[:8]:
        frames.append(await media.image_to_b64(img))
    if not frames:
        raise HTTPException(400, "Upload a kitchen video or up to 8 photos.")
    frames = frames[:8]

    content: list[dict] = []
    for i, b64 in enumerate(frames, 1):
        content.append({"type": "text", "text": f"Frame {i}:"})
        content.append(llm.image_block(b64))
    content.append({"type": "text", "text": f"Context: {note.strip()[:400] or 'none'}"})

    result = llm.complete_json(SYSTEM, content, lambda o: _validate(o, len(frames)), max_tokens=1600)
    result.update(scoring.hygiene_score(result["indicators"]))
    result["frames_analysed"] = len(frames)
    result["id"] = db.add_record("hygiene", {k: v for k, v in result.items() if k != "id"})
    return result
