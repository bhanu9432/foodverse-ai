"""FoodVerse AI API. Run: uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, db, llm
from .routers import audio, cooking, food, freshness, hygiene, insights, planner


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init()
    yield


app = FastAPI(title="FoodVerse AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

for r in (food, freshness, hygiene, cooking, planner, audio, insights):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"ok": True, "ai_configured": llm.configured(), "model": config.MODEL, "server_audio": audio.available()}


# If the React app has been built (npm run build), serve it from the same server.
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
