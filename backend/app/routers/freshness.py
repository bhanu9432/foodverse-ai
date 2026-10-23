"""Objective 4: classify freshness as Fresh, Moderately Fresh or Spoiled from visual characteristics."""
from fastapi import APIRouter, File, Form, UploadFile

from .. import db, llm, media, scoring
from ..util import num, text

router = APIRouter(prefix="/api/freshness", tags=["freshness"])

SYSTEM = """You are a food-safety specialist judging freshness from a photo.
Examine colour, texture, discolouration and surface patterns (mould, wilting, bruising, slime, shrivelling, \
dull or glossy surface, cut-surface browning, liquid pooling). Classify the food as exactly one of:
"Fresh", "Moderately Fresh", or "Spoiled".
Rules:
- A photo cannot show smell, taste or bacteria. If in doubt between two classes, choose the worse one.
- Visible mould, slime or heavy rot is always "Spoiled".
- Cooked food held warm for a long time cannot be judged as Fresh from looks alone: say so in the advice.
- Use the storage and days-held context if given.
Name the food. If the photo shows no food, set item to "none" and classification to "Spoiled" with confidence 0.
JSON shape:
{"item": str, "classification": "Fresh"|"Moderately Fresh"|"Spoiled", "confidence": number, \
"visual_signs": {"color": str, "texture": str, "discoloration": str, "surface_patterns": str}, \
"shelf_life_days": number, "advice": str}
"shelf_life_days" is your estimate of remaining safe days from now (0 if spoiled). "advice" is one or two sentences."""


def _validate(obj: dict) -> dict:
    if obj.get("classification") not in scoring.FRESHNESS_LABELS:
        raise ValueError("classification must be Fresh, Moderately Fresh or Spoiled")
    vs = obj.get("visual_signs") if isinstance(obj.get("visual_signs"), dict) else {}
    return {
        "item": text(obj.get("item"), 80, "Unknown"),
        "classification": obj["classification"],
        "confidence": num(obj.get("confidence"), 0, 1, 0.5),
        "visual_signs": {k: text(vs.get(k), 200) for k in ("color", "texture", "discoloration", "surface_patterns")},
        "shelf_life_days": num(obj.get("shelf_life_days"), 0, 60),
        "advice": text(obj.get("advice"), 500),
    }


@router.post("/analyze")
async def analyze(
    image: UploadFile = File(...),
    item_hint: str = Form(""),
    storage: str = Form("unknown"),
    days_held: float = Form(0),
    mould: bool = Form(False),
    sour_smell: bool = Form(False),
    slimy: bool = Form(False),
):
    b64 = await media.image_to_b64(image)
    ctx = f"Item (user says): {item_hint.strip()[:80] or 'not given'}. Stored: {storage[:20]}. Days held: {num(days_held, 0, 365)}."
    result = llm.complete_json(SYSTEM, [llm.image_block(b64), {"type": "text", "text": ctx}], _validate, max_tokens=900)

    flags = {"mould": mould, "sour_smell": sour_smell, "slimy": slimy}
    result = scoring.apply_freshness_safety(result, flags)
    if result.get("overridden_by_user_report"):
        result["advice"] = "You reported mould, a sour smell or slime. That makes it unsafe to eat. Do not taste it. " + result["advice"]
    result["disclaimer"] = "A photo cannot show bacteria, smell or taste. When in doubt, throw it out."
    result["flags"] = flags
    result["id"] = db.add_record("freshness", {k: v for k, v in result.items() if k != "id"})
    return result
