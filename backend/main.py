from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.detector import EnsembleDetector
from backend import db
from backend.routers import detect, metrics, alerts, stream


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB, load model if it exists
    await db.init_db()
    app.state.detector = EnsembleDetector.load(settings.model_path)
    if app.state.detector.is_trained:
        print(f"[startup] Loaded model from {settings.model_path}")
    else:
        print("[startup] No saved model found. POST /train to train.")
    yield
    # Shutdown: nothing to clean up (SQLite, joblib handles it)


app = FastAPI(
    title="Smart Grid IDS",
    description="Ensemble flooding-attack detector — Isolation Forest + Random Forest + SHAP",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(detect.router)
app.include_router(metrics.router)
app.include_router(alerts.router)
app.include_router(stream.router)
