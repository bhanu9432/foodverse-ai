# FoodVerse AI: Multimodal Food Intelligence Agent

A full-stack app that analyses food from photos, kitchen video, voice and text. React frontend, FastAPI backend, Claude for vision and reasoning, SQLite for history.

## What it does

| # | Objective | Where it lives |
|---|---|---|
| 1 | Multimodal platform (images, video, audio, text) | Food Scan accepts photo + typed or spoken note together. Hygiene accepts video. Voice works everywhere with a mic button. |
| 2 | Food recognition | `backend/app/routers/food.py`, `frontend/src/pages/FoodScan.jsx` |
| 3 | Nutrition and health score | Model estimates per-item nutrition. `backend/app/scoring.py` turns it into a 0-100 score with a visible breakdown. |
| 4 | Freshness: Fresh, Moderately Fresh, Spoiled | `routers/freshness.py`. Colour, texture, discolouration and surface patterns. Reported mould, smell or slime overrides the photo. |
| 5 | Kitchen hygiene from video | `routers/hygiene.py` + `media.py`. 8 frames are sampled with OpenCV and checked for gloves, hair cap, bare-hand contact, raw/cooked separation, surfaces, handwashing. |
| 6 | Smart cooking assistance | `routers/cooking.py`. Recipes from your ingredients, step timers, safe temperatures, and a chat that knows the current recipe. |
| 7 | Personalised, adaptive meal plans | `routers/planner.py`. Targets from your profile, a 7-day plan, and recent meal scans feed into the next plan. |
| 8 | Combine vision, audio and an LLM | Photo + transcribed voice note go into one model call. Audio uses `faster-whisper` on the server or the browser's speech recognition. |
| 9 | Full-stack architecture: React + FastAPI | `frontend/` (Vite + React), `backend/` (FastAPI, one router per capability). |
| 10 | Actionable insights | `routers/insights.py`, `Dashboard.jsx`. Alerts from rules, a 7-day chart, and an AI-written summary with action items. |

### Design rule: the model estimates, the code decides

Scores and safety decisions are deterministic code, not model opinion, so they are explainable and testable:

- **Health score**: starts at 60, adds points for protein share and fibre, subtracts for sugar, saturated fat, sodium and energy density.
- **Hygiene score**: weighted indicators. Critical gaps (gloves, bare hands, raw/cooked separation, handwashing) cap the grade at "Needs action". Indicators the camera cannot see are excluded, never guessed.
- **Freshness**: if you report mould, a sour smell or slime, the result becomes Spoiled whatever the photo shows.
- **Meal plan**: the server checks each day's calories and scales portions that miss your target by more than 6%. The scaling is shown to you.
- **Daily targets**: Mifflin-St Jeor equation.

## Run it

You need Python 3.10+ and Node 18+.

**1. Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # then put your ANTHROPIC_API_KEY in .env
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

Optional server-side speech-to-text (otherwise the browser's built-in speech recognition is used):

```bash
pip install -r requirements-audio.txt
```

**2. Frontend (development)**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite forwards `/api` to port 8000.

**3. One server for everything (demo or deployment)**

```bash
cd frontend && npm install && npm run build
cd ../backend && uvicorn app.main:app --port 8000
```

FastAPI serves the built React app at http://localhost:8000.

## Deploy (GitHub + Render, Docker)

GitHub Pages can only host static files, and FoodVerse needs the Python backend, so deploy the whole thing as one container.

1. Push this folder to a new GitHub repo (commands below).
2. On [render.com](https://render.com): **New > Blueprint**, pick the repo. `render.yaml` and the `Dockerfile` do the rest.
3. In the Render dashboard set `ANTHROPIC_API_KEY`. Your live URL is the **Demo link** for your project.

Any Docker host (Railway, Fly.io, Cloud Run) works the same way: `docker build -t foodverse .` then `docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... foodverse`.

**Before sharing the URL publicly:** anyone who opens it can spend your API credits. Set a monthly spend limit on the key, or keep the URL private. Free Render instances sleep when idle and lose the SQLite history on restart.

```bash
git init && git add . && git commit -m "FoodVerse AI"
git branch -M main
git remote add origin https://github.com/<your-username>/foodverse-ai.git
git push -u origin main
```

## Tests

```bash
cd backend
pytest
```

The tests replace the Claude call with canned replies, so they check everything around the model: input validation, scoring rules, the database, safety overrides, retries on malformed model output, and error codes. They do not check how accurate the model is. Judge that yourself with your own photos.

## API summary

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/food/analyze` | `image` (optional), `note` (optional, one required) |
| POST | `/api/freshness/analyze` | `image`, optional `item_hint`, `storage`, `days_held`, `mould`, `sour_smell`, `slimy` |
| POST | `/api/hygiene/analyze` | `video` and/or up to 8 `images`, optional `note` |
| POST | `/api/cooking/suggest` | ingredients, diet, allergies, time, servings |
| POST | `/api/cooking/chat` | messages and optional current recipe |
| GET/PUT | `/api/planner/profile` | saved profile |
| POST | `/api/planner/generate` | profile and optional adjustment text |
| POST | `/api/audio/transcribe` | `audio` file, needs `faster-whisper` |
| GET | `/api/insights` | dashboard numbers and alerts (`tz_offset` in minutes east of UTC) |
| POST | `/api/insights/summary` | AI-written summary and action items |
| GET/DELETE | `/api/records`, `/api/records/{id}` | scan history |
| GET | `/api/health` | server status, whether a key is set |

## Limits you should know about

- **Estimates, not measurements.** Portion size from a photo is a guess. Expect calories to be off by 20% or more, and use the confidence column.
- **Freshness from a photo cannot see bacteria, smell or taste.** The app says so on every result and errs toward the worse class.
- **Hygiene analysis looks at 8 frames.** It can miss things that happen between frames. Treat it as a spot check that supports, not replaces, a proper audit. Get staff consent before recording.
- **Privacy.** Photos and sampled video frames are sent to the Claude API for analysis. Uploaded video is deleted from the server right after frames are taken. Images are not stored. Scan results (not images) are saved in the local SQLite file.
- **Nutrition advice is general guidance, not medical advice.**
- Local use only as shipped. Before putting it on the internet add user accounts, rate limits and HTTPS.

## Project layout

```
backend/
  app/
    main.py            app, CORS, routers, serves the built frontend
    config.py          environment settings
    llm.py             Claude wrapper: JSON parsing, retry, error handling
    media.py           image validation and downscaling, video frame sampling
    scoring.py         health score, hygiene score, freshness override, energy targets
    db.py              SQLite: scan history and profile
    routers/           food, freshness, hygiene, cooking, planner, audio, insights
  tests/test_api.py
frontend/
  src/
    App.jsx            layout and navigation
    api.js             API client
    components.jsx     shared UI, voice input, step timer
    pages/             Dashboard, FoodScan, Freshness, Hygiene, Cooking, Planner
```
