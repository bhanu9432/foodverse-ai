"""API tests. The Claude call is replaced with canned replies, so these check everything around the model:
validation, scoring rules, database, safety overrides and error handling."""
import io
import json
import os
import sys
import tempfile

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import config, llm, scoring  # noqa: E402

config.DB_PATH = os.path.join(tempfile.mkdtemp(), "test.db")
from app.main import app  # noqa: E402

REPLIES: dict[str, str] = {}
CALLS: list[dict] = []


def fake_complete(system, content, max_tokens=2048, messages=None):
    CALLS.append({"system": system, "content": content, "messages": messages})
    for key, reply in REPLIES.items():
        if key in system:
            return reply if isinstance(reply, str) else json.dumps(reply)
    raise AssertionError("no canned reply for this prompt")


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(llm, "complete", fake_complete)
    monkeypatch.setattr(llm, "configured", lambda: True)
    CALLS.clear()
    REPLIES.clear()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def jpeg(color=(200, 150, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), color).save(buf, "JPEG")
    return buf.getvalue()


def mp4(path_hint="clip.mp4") -> bytes:
    path = os.path.join(tempfile.mkdtemp(), path_hint)
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10, (96, 72))
    for i in range(40):
        w.write(np.full((72, 96, 3), (i * 5) % 255, dtype=np.uint8))
    w.release()
    return open(path, "rb").read()


FOOD_REPLY = {"no_food": False, "notes": "Assumed 1 tsp ghee.", "items": [
    {"name": "Dal tadka", "estimated_grams": 200, "confidence": 0.82, "calories": 230, "protein_g": 12, "carbs_g": 30,
     "fat_g": 7, "fiber_g": 8, "sugar_g": 3, "sat_fat_g": 2, "sodium_mg": 400},
    {"name": "Chapati", "estimated_grams": 80, "confidence": 0.9, "calories": 240, "protein_g": 8, "carbs_g": 40,
     "fat_g": 5, "fiber_g": 5, "sugar_g": 1, "sat_fat_g": 1, "sodium_mg": 300}]}


# ---------- scoring rules ----------

def test_health_score_rewards_protein_and_fibre():
    good = scoring.health_score({"grams": 400, "calories": 450, "protein_g": 30, "carbs_g": 50, "fat_g": 12,
                                 "fiber_g": 12, "sugar_g": 5, "sat_fat_g": 3, "sodium_mg": 350})
    bad = scoring.health_score({"grams": 150, "calories": 700, "protein_g": 6, "carbs_g": 80, "fat_g": 38,
                                "fiber_g": 1, "sugar_g": 50, "sat_fat_g": 18, "sodium_mg": 2000})
    assert good["score"] > 75 > 40 > bad["score"]
    assert bad["breakdown"]["added_sugar"] < 0 and good["breakdown"]["fiber"] > 0


def test_hygiene_score_critical_caps_grade():
    inds = [{"key": "gloves", "status": "violation"}, {"key": "hair_cap", "status": "compliant"},
            {"key": "apron", "status": "compliant"}, {"key": "surface_cleanliness", "status": "compliant"}]
    r = scoring.hygiene_score(inds)
    assert r["grade"] == "Needs action" and r["critical"] == ["gloves"]
    assert scoring.hygiene_score([{"key": "gloves", "status": "not_visible"}])["score"] is None


def test_energy_targets_known_value():
    t = scoring.energy_targets("male", 28, 172, 68, "moderate", "maintain")
    assert t["bmr"] == 1620 and t["calories"] == round(1620 * 1.55)


# ---------- food ----------

def test_food_photo_and_note(client):
    REPLIES["registered dietitian"] = FOOD_REPLY
    r = client.post("/api/food/analyze", files={"image": ("meal.jpg", jpeg(), "image/jpeg")}, data={"note": "less oil"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["totals"]["calories"] == 470 and len(body["items"]) == 2
    assert 0 <= body["health"]["score"] <= 100 and body["id"]
    sent = CALLS[-1]["content"]
    assert sent[0]["type"] == "image" and "less oil" in sent[-1]["text"]


def test_food_text_only_and_validation(client):
    REPLIES["registered dietitian"] = FOOD_REPLY
    assert client.post("/api/food/analyze", data={"note": "dal and 2 rotis"}).status_code == 200
    assert client.post("/api/food/analyze", data={"note": ""}).status_code == 400
    bad = client.post("/api/food/analyze", files={"image": ("a.txt", b"hello", "text/plain")})
    assert bad.status_code == 415
    corrupt = client.post("/api/food/analyze", files={"image": ("a.jpg", b"not an image", "image/jpeg")})
    assert corrupt.status_code == 400


def test_food_no_food(client):
    REPLIES["registered dietitian"] = {"no_food": True, "items": [], "notes": ""}
    r = client.post("/api/food/analyze", files={"image": ("x.jpg", jpeg(), "image/jpeg")})
    assert r.json()["no_food"] is True and r.json()["health"] is None


def test_model_returns_garbage_then_fixes_itself(client):
    replies = iter(["sorry, here you go: nothing", json.dumps(FOOD_REPLY)])
    llm_calls = []

    def flaky(system, content, max_tokens=2048, messages=None):
        llm_calls.append(1)
        return next(replies)

    llm.complete = flaky
    r = client.post("/api/food/analyze", data={"note": "dal"})
    assert r.status_code == 200 and len(llm_calls) == 2


def test_model_keeps_failing_gives_502(client):
    llm.complete = lambda *a, **k: "not json at all"
    assert client.post("/api/food/analyze", data={"note": "dal"}).status_code == 502


# ---------- freshness ----------

FRESH_REPLY = {"item": "Banana", "classification": "Fresh", "confidence": 0.8, "shelf_life_days": 3, "advice": "Eat soon.",
               "visual_signs": {"color": "yellow", "texture": "firm", "discoloration": "none", "surface_patterns": "few spots"}}


def test_freshness_flags_override_photo(client):
    REPLIES["food-safety specialist"] = FRESH_REPLY
    ok = client.post("/api/freshness/analyze", files={"image": ("b.jpg", jpeg(), "image/jpeg")}, data={"item_hint": "banana"})
    assert ok.json()["classification"] == "Fresh"
    bad = client.post("/api/freshness/analyze", files={"image": ("b.jpg", jpeg(), "image/jpeg")}, data={"sour_smell": "true"})
    j = bad.json()
    assert j["classification"] == "Spoiled" and j["overridden_by_user_report"] and "unsafe" in j["advice"]


def test_freshness_rejects_unknown_label(client):
    REPLIES["food-safety specialist"] = {**FRESH_REPLY, "classification": "Pretty Good"}
    r = client.post("/api/freshness/analyze", files={"image": ("b.jpg", jpeg(), "image/jpeg")})
    assert r.status_code == 502


# ---------- hygiene ----------

HYG_REPLY = {"summary": "Gloves missing at the prep table.", "recommendations": ["Wear gloves for salads."],
             "indicators": [
                 {"key": "gloves", "status": "violation", "evidence": "bare hands on salad", "frames": [2, 3, 99]},
                 {"key": "hair_cap", "status": "compliant", "evidence": "hairnet on", "frames": [1]},
                 {"key": "apron", "status": "compliant", "evidence": "", "frames": []}]}


def test_hygiene_from_video(client):
    REPLIES["food-safety auditor"] = HYG_REPLY
    r = client.post("/api/hygiene/analyze", files={"video": ("k.mp4", mp4(), "video/mp4")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert 2 <= j["frames_analysed"] <= 8
    assert len(j["indicators"]) == len(scoring.HYGIENE_INDICATORS)  # missing keys are filled as not_visible
    gloves = next(i for i in j["indicators"] if i["key"] == "gloves")
    assert 99 not in gloves["frames"] and j["grade"] == "Needs action" and "gloves" in j["critical"]
    frame_labels = [c["text"] for c in CALLS[-1]["content"] if c["type"] == "text"]
    assert frame_labels[0] == "Frame 1:"


def test_hygiene_from_images_and_empty(client):
    REPLIES["food-safety auditor"] = HYG_REPLY
    files = [("images", (f"{i}.jpg", jpeg(), "image/jpeg")) for i in range(3)]
    assert client.post("/api/hygiene/analyze", files=files).json()["frames_analysed"] == 3
    assert client.post("/api/hygiene/analyze").status_code == 400
    assert client.post("/api/hygiene/analyze", files={"video": ("x.mp4", b"junk", "video/mp4")}).status_code == 400


# ---------- cooking ----------

RECIPE_REPLY = {"recipes": [{"name": "Dal tadka", "cuisine": "Indian", "time_minutes": 30, "servings": 2, "difficulty": "Easy",
    "ingredients": [{"item": "Toor dal", "quantity": "1 cup", "have": True}, {"item": "Garlic", "quantity": "4 cloves", "have": False}],
    "steps": [{"text": "Pressure cook dal.", "minutes": 15}, {"text": "Make tadka.", "minutes": 3}],
    "safety_temp_c": None, "tips": ["Use ghee."], "nutrition_per_serving": {"calories": 250, "protein_g": 12, "carbs_g": 35, "fat_g": 7}}]}


def test_cooking_suggest_and_chat(client):
    REPLIES["home-cooking assistant"] = RECIPE_REPLY
    r = client.post("/api/cooking/suggest", json={"ingredients": ["dal", "onion"], "diet": "vegetarian"})
    assert r.status_code == 200 and r.json()["recipes"][0]["missing"] == ["Garlic"]
    assert client.post("/api/cooking/suggest", json={"ingredients": []}).status_code == 422
    REPLIES["cooking coach"] = "Use a pinch of sugar."
    c = client.post("/api/cooking/chat", json={"messages": [{"role": "user", "content": "too sour"}], "recipe": r.json()["recipes"][0]})
    assert c.json()["reply"] == "Use a pinch of sugar." and "Dal tadka" in CALLS[-1]["system"]
    assert client.post("/api/cooking/chat", json={"messages": [{"role": "assistant", "content": "hi"}]}).status_code == 400


# ---------- planner ----------

def _plan(day_kcal):
    return {"rationale": "Fits your goal.", "days": [{"day": "x", "meals": [
        {"slot": s, "name": f"{s} dish", "portion": "1 plate", "calories": day_kcal / 4, "protein_g": 25, "carbs_g": 60, "fat_g": 15}
        for s in ("Breakfast", "Lunch", "Snack", "Dinner")]} for _ in range(7)]}


PROFILE = {"sex": "male", "age": 28, "height_cm": 172, "weight_kg": 68, "activity": "moderate", "goal": "maintain", "diet": "veg"}


def test_planner_scales_days_that_miss_target(client):
    REPLIES["7-day meal plan"] = _plan(1500)  # target is 2511
    r = client.post("/api/planner/generate", json={"profile": PROFILE, "adjust": "more protein"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["targets"]["calories"] == 2511 and len(j["days"]) == 7
    assert all(abs(d["target_gap_pct"]) <= 1 and d["scaled"] for d in j["days"])
    assert "more protein" in CALLS[-1]["content"]
    assert client.get("/api/planner/profile").json()["profile"]["age"] == 28


def test_planner_leaves_good_days_alone_and_rejects_bad_profile(client):
    REPLIES["7-day meal plan"] = _plan(2511)
    j = client.post("/api/planner/generate", json={"profile": PROFILE}).json()
    assert not any(d["scaled"] for d in j["days"])
    assert client.post("/api/planner/generate", json={"profile": {**PROFILE, "age": 5}}).status_code == 422


# ---------- audio, insights, records, health ----------

def test_audio_not_installed_gives_501(client, monkeypatch):
    from app.routers import audio
    monkeypatch.setattr(audio, "available", lambda: False)
    assert client.post("/api/audio/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")}).status_code == 501


def test_audio_transcribe_when_available(client, monkeypatch):
    from app.routers import audio
    monkeypatch.setattr(audio, "available", lambda: True)
    monkeypatch.setattr(audio, "transcribe_file", lambda p: "two rotis and dal")
    r = client.post("/api/audio/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")})
    assert r.json() == {"text": "two rotis and dal"}


def test_insights_alerts_and_summary(client):
    REPLIES["registered dietitian"] = FOOD_REPLY
    REPLIES["food-safety specialist"] = {**FRESH_REPLY, "classification": "Spoiled", "item": "Spinach", "advice": "Bin it."}
    REPLIES["food-safety auditor"] = HYG_REPLY
    client.post("/api/food/analyze", data={"note": "lunch"})
    client.post("/api/freshness/analyze", files={"image": ("s.jpg", jpeg(), "image/jpeg")})
    client.post("/api/hygiene/analyze", files={"images": ("k.jpg", jpeg(), "image/jpeg")})
    j = client.get("/api/insights", params={"tz_offset": 330}).json()
    assert j["today"]["calories"] >= 470 and j["targets"]["calories"] == 2511 and len(j["week"]) == 7
    levels = {a["level"] for a in j["alerts"]}
    assert "critical" in levels
    assert any("Spinach" in a["text"] for a in j["alerts"])
    REPLIES["nutrition and food-safety coach"] = "You are on track. Bin the spinach."
    assert "spinach" in client.post("/api/insights/summary").json()["summary"].lower()


def test_records_delete_and_health(client):
    recs = client.get("/api/records", params={"kind": "food"}).json()["records"]
    assert recs
    assert client.delete(f"/api/records/{recs[0]['id']}").status_code == 200
    assert client.delete(f"/api/records/{recs[0]['id']}").status_code == 404
    h = client.get("/api/health").json()
    assert h["ok"] and h["ai_configured"] and h["model"]


def test_no_api_key_gives_clear_503(client, monkeypatch):
    monkeypatch.undo()  # use the real llm.complete
    llm.complete = llm.__dict__["complete"]
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(llm, "_client", None)
    r = client.post("/api/food/analyze", data={"note": "dal"})
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.json()["detail"]
