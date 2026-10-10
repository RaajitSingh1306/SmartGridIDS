from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


# ── Input ─────────────────────────────────────────────────────────────────────

class GridRecord(BaseModel):
    Packet_Transmission_Rate_pps: float = Field(..., gt=0, description="Packets per second")
    Data_Volume_KBps: float = Field(..., gt=0, description="Data volume KB/s")
    Requests_per_SM: float = Field(..., gt=0, description="Requests per smart meter")
    Network_Latency_ms: float = Field(..., gt=0, description="Network latency ms")

    model_config = {"json_schema_extra": {
        "example": {
            "Packet_Transmission_Rate_pps": 350.2,
            "Data_Volume_KBps": 1720.5,
            "Requests_per_SM": 88.3,
            "Network_Latency_ms": 128.7,
        }
    }}


# ── Output ────────────────────────────────────────────────────────────────────

SeverityLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class DetectionResult(BaseModel):
    is_anomaly: bool
    severity: SeverityLevel
    ensemble_score: float = Field(..., description="Weighted vote [0–1]. ≥0.5 → anomaly.")
    if_score: float = Field(..., description="Isolation Forest anomaly score (more negative = worse)")
    rf_residual: float = Field(..., description="Absolute RF prediction error")
    rf_threshold: float = Field(..., description="Active residual threshold")
    if_pred: int = Field(..., description="IF prediction (0=normal, 1=anomaly)")
    rf_pred: int = Field(..., description="RF prediction (0=normal, 1=anomaly)")
    top_feature: str = Field(..., description="Feature with highest SHAP magnitude")
    top_shap_value: float


class BatchDetectionResult(BaseModel):
    total: int
    anomalies: int
    anomaly_rate: float
    results: list[DetectionResult]


# ── Alert log ─────────────────────────────────────────────────────────────────

class AlertRecord(BaseModel):
    id: int
    timestamp: datetime
    severity: SeverityLevel
    ensemble_score: float
    top_feature: str
    top_shap_value: float
    packet_rate: float
    data_volume: float
    requests_sm: float
    latency_ms: float


# ── Metrics ───────────────────────────────────────────────────────────────────

class ModelMetrics(BaseModel):
    is_trained: bool
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    accuracy: Optional[float] = None
    model_path: Optional[str] = None
    note: str = ""


class TrainResponse(BaseModel):
    status: str
    rows_used: int
    metrics: Optional[ModelMetrics] = None
