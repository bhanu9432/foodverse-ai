"""Objectives 1-3: multimodal food recognition and nutrition analysis with a health score."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import db, llm, media, scoring
from ..util import as_list, num, text

router = APIRouter(prefix="/api/food", tags=["food"])

SYSTEM = """You are a registered dietitian with expert food-recognition skills, focused on home-cooked and \
restaurant food from South Asia and around the world.
Identify every distinct dish or food item you can see or that the user's note describes. For each, estimate the \
portion weight in grams from visual cues (plate size, bowls, cutlery, typical servings) and give nutrition for \
THAT portion: calories, protein, carbohydrate, fat, fibre, sugars, saturated fat and sodium.
Use the user's note (typed or transcribed from speech) to adjust: cooking method, oil, sweeteners, brand, portion.
Be honest about uncertainty: lower the confidence (0 to 1) when items are hard to tell apart or portions are unclear.
If no food is visible and the note describes no food, return no_food true with an empty items list.
JSON shape:
{"no_food": false, "items": [{"name": str, "estimated_grams": number, "confidence": number, "calories": number, \
"protein_g": number, "carbs_g": number, "fat_g": number, "fiber_g": number, "sugar_g": number, \
"sat_fat_g": number, "sodium_mg": number}], "notes": str}
"notes" is one or two plain sentences on assumptions you made."""


def _validate(obj: dict) -> dict:
    if not isinstance(obj, dict):
        raise ValueError("expected an object")
    items = []
    for it in as_list(obj.get("items"))[:15]:
        if not isinstance(it, dict) or not it.get("name"):
            continue
        items.append({
            "name": text(it["name"], 80),
            "grams": num(it.get("estimated_grams"), 1, 3000, 100),
            "confidence": num(it.get("confidence"), 0, 1, 0.5),
            "calories": num(it.get("calories"), 0, 5000),
            "protein_g": num(it.get("protein_g"), 0, 300),
            "carbs_g": num(it.get("carbs_g"), 0, 600),
            "fat_g": num(it.get("fat_g"), 0, 300),
            "fiber_g": num(it.get("fiber_g"), 0, 100),
            "sugar_g": num(it.get("sugar_g"), 0, 400),
            "sat_fat_g": num(it.get("sat_fat_g"), 0, 150),
            "sodium_mg": num(it.get("sodium_mg"), 0, 20000),
        })
    return {"no_food": bool(obj.get("no_food")) or not items, "items": items, "notes": text(obj.get("notes"), 400)}


@router.post("/analyze")
async def analyze(image: UploadFile | None = File(None), note: str = Form("")):
    note = note.strip()[:600]
    if image is None and not note:
        raise HTTPException(400, "Add a photo, a typed description, or a voice note.")
    content: list[dict] = []
    if image is not None:
        content.append(llm.image_block(await media.image_to_b64(image)))
    content.append({"type": "text", "text": f"User note: {note}" if note else "No note. Analyse the photo."})

    result = llm.complete_json(SYSTEM, content, _validate, max_tokens=1800)
    if result["no_food"]:
        return {"id": None, **result, "totals": None, "health": None}

    totals = scoring.meal_totals(result["items"])
    health = scoring.health_score(totals)
    payload = {"items": result["items"], "totals": totals, "health": health, "notes": result["notes"],
               "had_photo": image is not None, "note": note}
    rec_id = db.add_record("food", payload)
    return {"id": rec_id, "no_food": False, **payload}
