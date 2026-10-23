"""Objective 7: personalised, adaptive meal plans. Targets are computed here; the model proposes meals;
the server checks the numbers and scales portions so every day lands on target."""
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import db, llm, scoring
from ..util import as_list, num, text

router = APIRouter(prefix="/api/planner", tags=["planner"])

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SLOTS = ["Breakfast", "Lunch", "Snack", "Dinner"]
TOLERANCE = 0.06


class Profile(BaseModel):
    sex: Literal["male", "female"]
    age: int = Field(ge=14, le=90)
    height_cm: float = Field(ge=120, le=220)
    weight_kg: float = Field(ge=35, le=200)
    activity: Literal["sedentary", "light", "moderate", "high"] = "moderate"
    goal: Literal["lose", "maintain", "gain"] = "maintain"
    diet: Literal["veg", "egg", "nonveg"] = "veg"
    allergies: str = Field("", max_length=200)
    dislikes: str = Field("", max_length=200)
    cuisine: str = Field("Indian", max_length=60)


class GenerateIn(BaseModel):
    profile: Profile
    adjust: str = Field("", max_length=400)


SYSTEM = f"""You are a dietitian creating a 7-day meal plan. Obey the diet, allergies and dislikes strictly. \
Use realistic dishes for the requested cuisine, with variety across the week (no dish more than twice).
Each day has exactly these meals in order: {', '.join(SLOTS)}. Give each meal calories, protein, carbs and fat for the stated portion.
Each day's calories must be within 5% of the daily target and protein at or above the protein target.
Diet meanings: veg = no meat, fish or eggs; egg = vegetarian plus eggs; nonveg = anything.
JSON shape:
{{"days": [{{"day": str, "meals": [{{"slot": str, "name": str, "portion": str, "calories": number, \
"protein_g": number, "carbs_g": number, "fat_g": number}}]}}], "rationale": str}}
"rationale" is two sentences on how the plan fits this person's goal."""


def _validate(obj: dict) -> dict:
    days = []
    for d in as_list(obj.get("days"))[:7]:
        meals = []
        for m in as_list(d.get("meals")) if isinstance(d, dict) else []:
            if isinstance(m, dict) and m.get("name"):
                meals.append({
                    "slot": m.get("slot") if m.get("slot") in SLOTS else "Meal",
                    "name": text(m["name"], 90), "portion": text(m.get("portion"), 60),
                    "calories": num(m.get("calories"), 0, 3000), "protein_g": num(m.get("protein_g"), 0, 250),
                    "carbs_g": num(m.get("carbs_g"), 0, 500), "fat_g": num(m.get("fat_g"), 0, 250),
                })
        if len(meals) < 3:
            raise ValueError("each day needs at least 3 meals")
        days.append({"meals": meals})
    if len(days) != 7:
        raise ValueError("need exactly 7 days")
    for i, d in enumerate(days):
        d["day"] = DAYS[i]
    return {"days": days, "rationale": text(obj.get("rationale"), 500)}


def _totals(meals: list[dict]) -> dict:
    return {k: round(sum(m[k] for m in meals)) for k in ("calories", "protein_g", "carbs_g", "fat_g")}


def _fit_days(days: list[dict], target: int) -> list[dict]:
    """Scale any day that misses the calorie target by more than the tolerance. Scaling is shown to the user."""
    for d in days:
        tot = _totals(d["meals"])
        d["scaled"] = False
        if tot["calories"] and abs(tot["calories"] - target) / target > TOLERANCE:
            f = target / tot["calories"]
            for m in d["meals"]:
                for k in ("calories", "protein_g", "carbs_g", "fat_g"):
                    m[k] = round(m[k] * f)
                m["portion"] = (m["portion"] + " " if m["portion"] else "") + f"(portion x{f:.2f})"
            d["scaled"] = True
        d["totals"] = _totals(d["meals"])
        d["target_gap_pct"] = round((d["totals"]["calories"] - target) / target * 100, 1)
    return days


def _recent_intake() -> dict | None:
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
    recs = db.list_records("food", since=since)
    if not recs:
        return None
    by_day: dict[str, float] = {}
    for r in recs:
        by_day[r["created_at"][:10]] = by_day.get(r["created_at"][:10], 0) + r["data"]["totals"]["calories"]
    scores = [r["data"]["health"]["score"] for r in recs]
    return {"avg_daily_kcal": round(sum(by_day.values()) / len(by_day)), "days_logged": len(by_day),
            "avg_health_score": round(sum(scores) / len(scores))}


@router.get("/profile")
def get_profile():
    return {"profile": db.get_setting("profile")}


@router.put("/profile")
def put_profile(p: Profile):
    db.set_setting("profile", p.model_dump())
    return {"profile": p.model_dump(), "targets": scoring.energy_targets(p.sex, p.age, p.height_cm, p.weight_kg, p.activity, p.goal)}


@router.post("/generate")
def generate(body: GenerateIn):
    p = body.profile
    db.set_setting("profile", p.model_dump())
    t = scoring.energy_targets(p.sex, p.age, p.height_cm, p.weight_kg, p.activity, p.goal)

    recent = _recent_intake()
    adaptive = ""
    if recent:
        adaptive = (f"Adaptive context from the last 7 days of logged meals: average {recent['avg_daily_kcal']} kcal on "
                    f"{recent['days_logged']} logged day(s), average meal health score {recent['avg_health_score']}/100. "
                    "Improve on this where it helps the goal.")
    prompt = (f"Daily target: {t['calories']} kcal, protein at least {t['protein_g']} g, carbs about {t['carbs_g']} g, fat about {t['fat_g']} g.\n"
              f"Person: {p.sex}, {p.age}, goal {p.goal}. Diet: {p.diet}. Cuisine: {p.cuisine}. "
              f"Allergies: {p.allergies or 'none'}. Dislikes: {p.dislikes or 'none'}.\n{adaptive}\n"
              f"Adjustment requested: {body.adjust or 'none'}")
    plan = llm.complete_json(SYSTEM, prompt, _validate, max_tokens=6000)
    plan["days"] = _fit_days(plan["days"], t["calories"])
    return {"targets": t, "adaptive_note": adaptive or None, **plan}
