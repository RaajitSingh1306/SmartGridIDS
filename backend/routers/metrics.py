from fastapi import APIRouter, Request
from backend.schemas import ModelMetrics, TrainResponse
from backend.config import settings
from backend.data_gen import load_dataset
from backend.detector import EnsembleDetector

router = APIRouter(tags=["model"])


@router.post("/train", response_model=TrainResponse)
async def train(request: Request):
    df, is_real = load_dataset(settings.data_path)
    det = EnsembleDetector(
        if_n_estimators=settings.if_n_estimators,
        rf_n_estimators=settings.rf_n_estimators,
        if_contamination=settings.if_contamination,
        threshold_percentile=settings.rf_threshold_percentile,
        if_weight=settings.ensemble_if_weight,
    )
    train_metrics = det.train(df)
    det.save(settings.model_path)
    request.app.state.detector = det

    metrics = ModelMetrics(
        is_trained=True,
        model_path=str(settings.model_path),
        note="real data" if is_real else "synthetic data (CSV not found)",
        **train_metrics,
    )
    return TrainResponse(status="ok", rows_used=len(df), metrics=metrics)


@router.get("/metrics", response_model=ModelMetrics)
async def get_metrics(request: Request):
    det = request.app.state.detector
    if not det.is_trained:
        return ModelMetrics(is_trained=False, note="Not trained yet.")
    return ModelMetrics(
        is_trained=True,
        model_path=str(settings.model_path),
        **det.train_metrics,
    )


@router.get("/health")
async def health(request: Request):
    det = request.app.state.detector
    return {
        "status": "ok",
        "trained": det.is_trained,
        "rf_threshold": det.rf_threshold,
        "if_weight": det.if_weight,
    }
