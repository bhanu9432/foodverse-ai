"""Deterministic scoring rules. The model estimates what is on the plate; these rules turn
that into numbers, so scores are explainable and testable rather than a model's opinion."""
from dataclasses import dataclass


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ---------- nutrition and health score ----------

def meal_totals(items: list[dict]) -> dict:
    keys = ["grams", "calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sat_fat_g", "sodium_mg"]
    return {k: round(sum(float(i.get(k, 0) or 0) for i in items), 1) for k in keys}


def health_score(t: dict) -> dict:
    """0-100 score for a meal. Starts at 60, then adds or subtracts for six measurable factors."""
    kcal = max(t["calories"], 1)
    protein_share = t["protein_g"] * 4 / kcal
    fiber_per_100 = t["fiber_g"] / kcal * 100
    sugar_share = t["sugar_g"] * 4 / kcal
    sat_share = t["sat_fat_g"] * 9 / kcal
    sodium_per_100 = t["sodium_mg"] / kcal * 100
    density = t["calories"] / t["grams"] if t["grams"] > 0 else 1.5

    parts = {
        "protein": round(20 * clamp(protein_share / 0.25, 0, 1), 1),
        "fiber": round(20 * clamp(fiber_per_100 / 2.5, 0, 1), 1),
        "added_sugar": round(-20 * clamp(sugar_share / 0.25, 0, 1), 1),
        "saturated_fat": round(-15 * clamp((sat_share - 0.05) / 0.15, 0, 1), 1),
        "sodium": round(-15 * clamp((sodium_per_100 - 100) / 200, 0, 1), 1),
        "energy_density": round(-10 * clamp((density - 1.5) / 3.5, 0, 1), 1),
    }
    score = int(round(clamp(60 + sum(parts.values()), 0, 100)))
    label = "Excellent" if score >= 80 else "Good" if score >= 65 else "Fair" if score >= 50 else "Poor"
    return {"score": score, "label": label, "breakdown": parts}


# ---------- freshness ----------

FRESHNESS_LABELS = ("Fresh", "Moderately Fresh", "Spoiled")


def apply_freshness_safety(result: dict, flags: dict) -> dict:
    """User-reported smell, slime or mould overrides the picture: those cannot be seen in a photo."""
    if flags.get("mould") or flags.get("sour_smell") or flags.get("slimy"):
        if result["classification"] != "Spoiled":
            result["classification"] = "Spoiled"
            result["overridden_by_user_report"] = True
    return result


# ---------- hygiene ----------

# (indicator key, label, weight). A violation costs its weight; "not visible" is left out of the score.
HYGIENE_INDICATORS = [
    ("gloves", "Gloves worn when handling ready-to-eat food", 3),
    ("hair_cap", "Hair cap or hairnet worn", 2),
    ("apron", "Clean apron or uniform", 1),
    ("bare_hand_contact", "No bare-hand contact with ready-to-eat food", 3),
    ("raw_cooked_separation", "Raw and cooked food kept apart", 3),
    ("surface_cleanliness", "Work surfaces and tools look clean", 2),
    ("handwashing", "Handwashing observed when needed", 3),
    ("food_covered", "Food covered or stored properly", 1),
]
HYGIENE_STATUSES = ("compliant", "violation", "not_visible")


def hygiene_score(indicators: list[dict]) -> dict:
    weights = {k: w for k, _, w in HYGIENE_INDICATORS}
    got = lost = 0.0
    critical = []
    for ind in indicators:
        w = weights.get(ind["key"], 1)
        if ind["status"] == "compliant":
            got += w
        elif ind["status"] == "violation":
            lost += w
            if w >= 3:
                critical.append(ind["key"])
    seen = got + lost
    score = None if seen == 0 else int(round(100 * got / seen))
    if score is None:
        grade = "Not enough visible"
    elif critical:
        grade = "Needs action"
    else:
        grade = "Good" if score >= 90 else "Fair" if score >= 75 else "Needs action"
    return {"score": score, "grade": grade, "critical": critical}


# ---------- energy targets ----------

ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "high": 1.725}


def energy_targets(sex: str, age: int, height_cm: float, weight_kg: float, activity: str, goal: str) -> dict:
    """Mifflin-St Jeor resting energy, scaled by activity, then adjusted for the goal."""
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if sex == "male" else -161)
    tdee = bmr * ACTIVITY[activity]
    adjust = {"lose": -450, "maintain": 0, "gain": 300}[goal]
    floor = 1500 if sex == "male" else 1200
    kcal = max(floor, tdee + adjust)
    per_kg = {"lose": 1.8, "maintain": 1.4, "gain": 1.8}[goal]
    protein = weight_kg * per_kg
    fat = kcal * 0.27 / 9
    carbs = max(0.0, (kcal - protein * 4 - fat * 9) / 4)
    return {
        "bmr": round(bmr), "tdee": round(tdee), "calories": round(kcal),
        "protein_g": round(protein), "carbs_g": round(carbs), "fat_g": round(fat),
    }


@dataclass
class Alert:
    level: str   # info | warn | critical
    text: str

    def dict(self) -> dict:
        return {"level": self.level, "text": self.text}
