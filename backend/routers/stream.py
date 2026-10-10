"""WebSocket endpoint that replays the dataset row-by-row at configurable speed.

Clients connect to ws://host:8000/ws/stream?delay_ms=500
Each message is a JSON DetectionResult + the raw record values.
"""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Request
from backend.data_gen import load_dataset
from backend.config import settings
from backend import db

router = APIRouter(tags=["stream"])


@router.websocket("/ws/stream")
async def stream(
    websocket: WebSocket,
    delay_ms: int = Query(500, ge=100, le=5000),
):
    await websocket.accept()
    det = websocket.app.state.detector

    if not det.is_trained:
        await websocket.send_json({"error": "Model not trained"})
        await websocket.close()
        return

    df, _ = load_dataset(settings.data_path)
    delay  = delay_ms / 1000.0

    try:
        for _, row in df.iterrows():
            record = {
                "Packet_Transmission_Rate_pps": float(row["Packet_Transmission_Rate_pps"]),
                "Data_Volume_KBps":             float(row["Data_Volume_KBps"]),
                "Requests_per_SM":              float(row["Requests_per_SM"]),
                "Network_Latency_ms":           float(row["Network_Latency_ms"]),
            }
            result = det.predict_one(record)
            if result["is_anomaly"]:
                await db.insert_alert(result, record)
            payload = {**result, **record}
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(delay)

        await websocket.send_json({"status": "stream_complete"})
    except WebSocketDisconnect:
        pass
