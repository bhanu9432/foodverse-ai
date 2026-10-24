# FoodVerse AI: Multimodal Food Intelligence Agent

FoodVerse AI is a web app that looks at food from photos, kitchen videos, typed text and voice, and turns what it sees into useful answers: what the food is, how healthy it is, whether it is still safe to eat, whether a kitchen follows hygiene rules, what to cook, and what to eat this week.

**Live demo:** https://foodverse-ai-tqgq.onrender.com
(The free server sleeps when idle, so the first load can take about a minute.)

## Features

| Module | What it does |
|---|---|
| Food Scan | Upload a food photo and/or describe or speak it. Detects dishes, estimates portion, calories, protein, carbs, fat, fibre, sugar, sodium, and gives a 0-100 health score with a breakdown. |
| Freshness | Classifies food as Fresh, Moderately Fresh or Spoiled from colour, texture, discolouration and surface patterns. Reported mould, sour smell or slime overrides the photo. |
| Kitchen Hygiene | Samples 8 frames from a kitchen video and checks gloves, hair cap, bare-hand contact, raw/cooked separation, surfaces and handwashing. Produces a score and recommendations. |
| Smart Cooking | Suggests recipes from the ingredients you have, with steps, timers and safe temperatures, plus a chat assistant for questions while cooking. |
| Meal Planner | Calculates daily targets from your profile (Mifflin-St Jeor equation) and builds a 7-day plan that adapts to your recent meal scans. |
| Dashboard | Shows alerts, a 7-day trend chart and an AI-written summary with action items. |

## How it works

1. The React frontend sends images, video, audio or text to the FastAPI backend.
2. The backend prepares the media (resizes images, samples video frames) and sends it to an AI model.
3. The model estimates what it sees. **Rule-based code then decides the scores**: the health score, hygiene score, freshness override and calorie targets are plain Python rules in `backend/app/scoring.py`, so they are explainable and testable.
4. Results are saved in a small SQLite database and shown as dashboards and alerts.

## Tech stack

- **Frontend:** React 18, Vite
- **Backend:** Python, FastAPI, OpenCV, Pillow, SQLite
- **AI:** Claude, Gemini or OpenRouter free models (set whichever key you have)
- **Deployment:** Docker, Render

## Run it locally

You need Python 3.10+ and Node 18+.

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # then add one AI key (see below)
uvicorn app.main:app --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev                     # open http://localhost:5173
```

AI keys (set one in `backend/.env`): `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY` (free) or `GEMINI_API_KEY` (free).

## Tests

```bash
cd backend
pytest
```

The tests replace the AI call with fixed replies, so they check validation, scoring rules, the database and error handling, not the AI's accuracy.

## Limits

- Calories and portions from a photo are estimates and can be off by 20% or more.
- A photo cannot show smell, taste or bacteria, so freshness results lean toward the safer answer.
- Hygiene analysis looks at 8 frames, so it can miss events between frames. It is a spot check, not an audit.
- Photos and sampled frames are sent to the AI provider. Nutrition advice is general guidance, not medical advice.

## Project structure

```
backend/app/   main.py, llm.py (AI wrapper), scoring.py (rules), media.py, db.py, routers/ (one file per feature)
frontend/src/  App.jsx, api.js, components.jsx, pages/ (one page per feature)
```

## Credits

Built with AI assistance (Claude). I reviewed, tested and deployed the project.
