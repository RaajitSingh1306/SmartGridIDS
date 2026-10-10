from fastapi import APIRouter, HTTPException, Request
from backend.schemas import GridRecord, DetectionResult, BatchDetectionResult
from backend import db

router = APIRouter(prefix="/detect", tags=["detection"])


def _get_detector(request: Request):
    det = request.app.state.detector
    if not det.is_trained:
        raise HTTPException(503, "Model not trained. POST /train first.")
    return det


@router.post("", response_model=DetectionResult)
async def detect_one(record: GridRecord, request: Request):
    det = _get_detector(request)
    result = det.predict_one(record.model_dump())
    if result["is_anomaly"]:
        await db.insert_alert(result, record.model_dump())
    return result


@router.post("/batch", response_model=BatchDetectionResult)
async def detect_batch(records: list[GridRecord], request: Request):
    if not records:
        raise HTTPException(400, "Empty batch.")
    det = _get_detector(request)
    raw = [r.model_dump() for r in records]
    results = det.predict_batch(raw)
    # Persist anomalies
    for res, rec in zip(results, raw):
        if res["is_anomaly"]:
            await db.insert_alert(res, rec)
    anomalies = sum(1 for r in results if r["is_anomaly"])
    return BatchDetectionResult(
        total=len(results),
        anomalies=anomalies,
        anomaly_rate=round(anomalies / len(results), 4),
        results=results,
    )
