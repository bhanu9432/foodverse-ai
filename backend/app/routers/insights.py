"""Objective 10: actionable insights. Numbers and alerts come from rules over saved scans;
the model only writes the plain-language summary from those numbers."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from .. import db, llm, scoring
from ..util import text

router = APIRouter(prefix="/api", tags=["insights"])


def _local(created_at: str, offset_min: int) -> datetime:
    return datetime.fromisoformat(created_at) + timedelta(minutes=offset_min)


def build_insights(offset_min: int = 0) -> dict:
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc + timedelta(minutes=offset_min)
    midnight_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start_utc = (midnight_local - timedelta(days=6) - timedelta(minutes=offset_min)).replace(tzinfo=timezone.utc)

    food = db.list_records("food", since=week_start_utc.isoformat(timespec="seconds"), limit=500)
    days = [(midnight_local - timedelta(days=i)).date() for i in range(6, -1, -1)]
    kcal_by_day = {d: 0.0 for d in days}
    today = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "meals": 0}
    for r in food:
        d = _local(r["created_at"], offset_min).date()
        t = r["data"]["totals"]
        if d in kcal_by_day:
            kcal_by_day[d] += t["calories"]
        if d == midnight_local.date():
            for k in ("calories", "protein_g", "carbs_g", "fat_g"):
                today[k] += t[k]
            today["meals"] += 1
    today = {k: round(v) for k, v in today.items()}
    scores = [r["data"]["health"]["score"] for r in food]

    profile = db.get_setting("profile")
    targets = None
    if profile:
        targets = scoring.energy_targets(profile["sex"], profile["age"], profile["height_cm"],
                                         profile["weight_kg"], profile["activity"], profile["goal"])

    fresh_cut = (now_utc - timedelta(hours=48)).isoformat(timespec="seconds")
    fresh = [r for r in db.list_records("freshness", since=fresh_cut, limit=50) if r["data"]["classification"] != "Fresh"]
    hyg = db.list_records("hygiene", limit=5)

    alerts: list[scoring.Alert] = []
    for r in fresh:
        d = r["data"]
        lvl = "critical" if d["classification"] == "Spoiled" else "warn"
        alerts.append(scoring.Alert(lvl, f"{d['item']} looks {d['classification'].lower()}. {d['advice']}".strip()))
    if hyg:
        h = hyg[0]["data"]
        if h.get("critical"):
            names = [i["label"] for i in h["indicators"] if i["key"] in h["critical"] and i["status"] == "violation"]
            alerts.append(scoring.Alert("critical", "Hygiene violations in the latest kitchen check: " + "; ".join(names) + "."))
        elif h.get("grade") == "Needs action":
            alerts.append(scoring.Alert("warn", f"Latest kitchen hygiene score is {h.get('score')}/100."))
    if targets and today["meals"]:
        if today["calories"] > targets["calories"] * 1.15:
            alerts.append(scoring.Alert("warn", f"Today's intake ({today['calories']} kcal) is over your {targets['calories']} kcal target."))
        if today["meals"] >= 3 and today["protein_g"] < targets["protein_g"] * 0.6:
            alerts.append(scoring.Alert("info", f"Protein is low so far today ({today['protein_g']} g of {targets['protein_g']} g)."))
    if scores and sum(scores) / len(scores) < 50:
        alerts.append(scoring.Alert("warn", "Your average meal health score this week is below 50. Check the breakdown on recent scans."))

    return {
        "today": today, "targets": targets,
        "week": [{"date": d.isoformat(), "calories": round(v)} for d, v in kcal_by_day.items()],
        "avg_health_score": round(sum(scores) / len(scores)) if scores else None,
        "meals_this_week": len(food),
        "hygiene_trend": [{"created_at": r["created_at"], "score": r["data"].get("score")} for r in reversed(hyg)],
        "alerts": [a.dict() for a in alerts],
    }


@router.get("/insights")
def insights(tz_offset: int = Query(0, ge=-840, le=840, description="Minutes east of UTC")):
    return build_insights(tz_offset)


@router.post("/insights/summary")
def summary(tz_offset: int = Query(0, ge=-840, le=840)):
    data = build_insights(tz_offset)
    if not data["meals_this_week"] and not data["hygiene_trend"]:
        raise HTTPException(400, "Scan a meal or run a kitchen check first, then ask for a summary.")
    system = ("You are a friendly nutrition and food-safety coach. From the JSON the user gives you, write: a 3 sentence summary, "
              "then up to 4 short action items for the next 24 hours. Use only the numbers provided. Do not diagnose any condition. "
              "Plain text, no markdown headings.")
    reply = llm.complete(system, "Data: " + text(str(data), 4000), max_tokens=500)
    return {"summary": reply.strip()}


@router.get("/records")
def records(kind: str | None = None, limit: int = Query(20, ge=1, le=100)):
    return {"records": db.list_records(kind, limit=limit)}


@router.delete("/records/{rec_id}")
def remove(rec_id: int):
    if not db.delete_record(rec_id):
        raise HTTPException(404, "Record not found.")
    return {"ok": True}
