"""Objective 6: recipes, ingredient lists, cooking steps and contextual cooking guidance."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import llm
from ..util import as_list, num, text

router = APIRouter(prefix="/api/cooking", tags=["cooking"])

SAFETY = ("Food safety rules you always follow: poultry 74 C, minced meat 71 C, fish 63 C, reheated leftovers 74 C, "
          "never leave cooked food out over 2 hours, keep raw and cooked separate. Mention a safe temperature when it applies.")

SUGGEST_SYSTEM = f"""You are a practical home-cooking assistant. Suggest exactly 3 recipes the user can cook with the \
ingredients they have, respecting diet, allergies and time limit. Assume basic pantry items (oil, salt, common spices, water). \
Prefer recipes that use what they have; list anything else as missing. Vary the three (different methods or cuisines).
{SAFETY}
JSON shape:
{{"recipes": [{{"name": str, "cuisine": str, "time_minutes": number, "servings": number, "difficulty": "Easy"|"Medium"|"Hard", \
"ingredients": [{{"item": str, "quantity": str, "have": boolean}}], \
"steps": [{{"text": str, "minutes": number}}], "safety_temp_c": number|null, "tips": [str], \
"nutrition_per_serving": {{"calories": number, "protein_g": number, "carbs_g": number, "fat_g": number}}}}]}}
Each step is one clear action; "minutes" is the timer length or 0 if none. Give 1 to 3 tips."""

CHAT_SYSTEM = f"""You are a friendly, concise cooking coach inside a kitchen app. Answer the user's cooking question using the \
recipe context if one is given. Give substitutions, fixes, timing and technique. Keep answers under 120 words unless asked for more.
{SAFETY}"""


class SuggestIn(BaseModel):
    ingredients: list[str] = Field(min_length=1, max_length=40)
    diet: Literal["any", "vegetarian", "eggetarian", "vegan"] = "any"
    allergies: str = Field("", max_length=200)
    max_minutes: int = Field(45, ge=5, le=240)
    servings: int = Field(2, ge=1, le=12)
    note: str = Field("", max_length=300)


class ChatMsg(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1500)


class ChatIn(BaseModel):
    messages: list[ChatMsg] = Field(min_length=1, max_length=20)
    recipe: dict | None = None


def _validate_recipes(obj: dict) -> dict:
    out = []
    for r in as_list(obj.get("recipes"))[:3]:
        if not isinstance(r, dict) or not r.get("name"):
            continue
        steps = [{"text": text(s.get("text"), 300), "minutes": num(s.get("minutes"), 0, 480)}
                 for s in as_list(r.get("steps")) if isinstance(s, dict) and s.get("text")]
        if not steps:
            continue
        ings = [{"item": text(i.get("item"), 60), "quantity": text(i.get("quantity"), 40), "have": bool(i.get("have"))}
                for i in as_list(r.get("ingredients")) if isinstance(i, dict) and i.get("item")]
        nut = r.get("nutrition_per_serving") if isinstance(r.get("nutrition_per_serving"), dict) else {}
        temp = r.get("safety_temp_c")
        out.append({
            "name": text(r["name"], 80), "cuisine": text(r.get("cuisine"), 40),
            "time_minutes": num(r.get("time_minutes"), 1, 480, 30), "servings": num(r.get("servings"), 1, 24, 2),
            "difficulty": r.get("difficulty") if r.get("difficulty") in ("Easy", "Medium", "Hard") else "Medium",
            "ingredients": ings, "missing": [i["item"] for i in ings if not i["have"]],
            "steps": steps, "safety_temp_c": num(temp, 40, 100) if temp not in (None, "") else None,
            "tips": [text(t, 200) for t in as_list(r.get("tips"))[:3]],
            "nutrition_per_serving": {k: num(nut.get(k), 0, 5000) for k in ("calories", "protein_g", "carbs_g", "fat_g")},
        })
    if not out:
        raise ValueError("no usable recipes")
    return {"recipes": out}


@router.post("/suggest")
def suggest(body: SuggestIn):
    prompt = (f"Ingredients I have: {', '.join(i.strip() for i in body.ingredients if i.strip())}.\n"
              f"Diet: {body.diet}. Allergies: {body.allergies or 'none'}. Max time: {body.max_minutes} minutes. "
              f"Servings: {body.servings}. Extra: {body.note or 'none'}.")
    return llm.complete_json(SUGGEST_SYSTEM, prompt, _validate_recipes, max_tokens=3500)


@router.post("/chat")
def chat(body: ChatIn):
    if body.messages[-1].role != "user":
        raise HTTPException(400, "The last message must be from the user.")
    system = CHAT_SYSTEM
    if body.recipe:
        names = text(body.recipe.get("name"), 80)
        steps = "; ".join(text(s.get("text"), 120) for s in as_list(body.recipe.get("steps"))[:12] if isinstance(s, dict))
        system += f"\nCurrent recipe: {names}. Steps: {steps}"
    msgs = [{"role": m.role, "content": m.content} for m in body.messages]
    return {"reply": llm.complete(system, "", max_tokens=500, messages=msgs).strip()}
