"""
EnsembleDetector — weighted vote of Isolation Forest and RF Regressor.

  score = w_IF * if_pred + w_RF * rf_pred
  anomaly if score >= 0.5

Upgrades over the paper:
  - RobustScaler instead of StandardScaler (less sensitive to attack outliers)
  - Ensemble vote instead of separate evaluation
  - SHAP per-prediction (TreeExplainer, no overhead beyond RF inference)
  - 4-level severity from composite IF score + RF residual magnitude
  - Auto threshold calibration on retrain
"""

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
import shap
from pathlib import Path
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
from sklearn.preprocessing import RobustScaler
from typing import Optional

FEATURES = [
    "Packet_Transmission_Rate_pps",
    "Data_Volume_KBps",
    "Requests_per_SM",
    "Network_Latency_ms",
]
RF_TARGET   = "Packet_Transmission_Rate_pps"
RF_FEATURES = [f for f in FEATURES if f != RF_TARGET]


class EnsembleDetector:
    def __init__(
        self,
        if_n_estimators: int = 200,
        rf_n_estimators: int = 200,
        if_contamination: float = 0.05,
        threshold_percentile: float = 95.0,
        if_weight: float = 0.6,
    ):
        self.if_n_estimators     = if_n_estimators
        self.rf_n_estimators     = rf_n_estimators
        self.if_contamination    = if_contamination
        self.threshold_pct       = threshold_percentile
        self.if_weight           = if_weight
        self.rf_weight           = 1.0 - if_weight

        self.scaler: Optional[RobustScaler]              = None
        self.if_model: Optional[IsolationForest]          = None
        self.rf_model: Optional[RandomForestRegressor]    = None
        self.rf_threshold: Optional[float]                = None
        self.shap_explainer                               = None
        self.train_metrics: dict                          = {}
        self.is_trained: bool                             = False

    # ── Training ──────────────────────────────────────────────────────────────

    def train(self, df: pd.DataFrame) -> dict:
        X_all = df[FEATURES].values.astype(float)
        X_rf  = df[RF_FEATURES].values.astype(float)
        y     = df[RF_TARGET].values.astype(float)

        # Scale full feature set for IF
        self.scaler = RobustScaler()
        X_scaled = self.scaler.fit_transform(X_all)

        # Isolation Forest — unsupervised, uses all features
        self.if_model = IsolationForest(
            n_estimators=self.if_n_estimators,
            contamination=self.if_contamination,
            random_state=42,
        )
        self.if_model.fit(X_scaled)

        # Random Forest Regressor — supervised residual path
        self.rf_model = RandomForestRegressor(
            n_estimators=self.rf_n_estimators,
            max_features="sqrt",
            random_state=42,
            n_jobs=-1,
        )
        self.rf_model.fit(X_rf, y)
        y_hat = self.rf_model.predict(X_rf)
        residuals = np.abs(y - y_hat)
        self.rf_threshold = float(np.percentile(residuals, self.threshold_pct))

        # SHAP — fit once on training data (fast for TreeExplainer)
        self.shap_explainer = shap.TreeExplainer(self.rf_model)

        # Evaluate on labelled data if available
        if "Anomaly" in df.columns:
            labels = df["Anomaly"].values.astype(int)
            preds  = self._batch_vote(X_scaled, X_rf, y, y_hat, residuals)
            self.train_metrics = _metrics(labels, preds)

        self.is_trained = True
        return self.train_metrics

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict_one(self, record: dict) -> dict:
        x_all = np.array([[record[f] for f in FEATURES]], dtype=float)
        x_rf  = np.array([[record[f] for f in RF_FEATURES]], dtype=float)
        x_sc  = self.scaler.transform(x_all)

        # IF
        if_score = float(self.if_model.score_samples(x_sc)[0])
        if_pred  = int(self.if_model.predict(x_sc)[0] == -1)

        # RF residual
        y_hat    = float(self.rf_model.predict(x_rf)[0])
        residual = abs(record[RF_TARGET] - y_hat)
        rf_pred  = int(residual > self.rf_threshold)

        # Ensemble vote
        ens_score   = self.if_weight * if_pred + self.rf_weight * rf_pred
        is_anomaly  = ens_score >= 0.5

        # SHAP (regressor → single array of shape [n_features])
        shap_vals = self.shap_explainer.shap_values(x_rf, check_additivity=False)[0]
        top_idx   = int(np.argmax(np.abs(shap_vals)))

        return {
            "is_anomaly":      bool(is_anomaly),
            "severity":        self._severity(if_score, residual),
            "ensemble_score":  round(float(ens_score), 3),
            "if_score":        round(if_score, 4),
            "rf_residual":     round(float(residual), 4),
            "rf_threshold":    round(float(self.rf_threshold), 4),
            "if_pred":         if_pred,
            "rf_pred":         rf_pred,
            "top_feature":     RF_FEATURES[top_idx],
            "top_shap_value":  round(float(shap_vals[top_idx]), 4),
        }

    def predict_batch(self, records: list[dict]) -> list[dict]:
        return [self.predict_one(r) for r in records]

    # ── Severity ──────────────────────────────────────────────────────────────

    def _severity(self, if_score: float, residual: float) -> str:
        """Composite score from both models' anomaly magnitudes.

        IF score is negative; more negative → more isolated → more anomalous.
        RF residual is absolute; higher → further from expected → more anomalous.
        """
        norm_if = min(1.0, max(0.0, -if_score / 0.6))
        norm_rf = min(1.0, residual / (self.rf_threshold * 4))
        c = 0.6 * norm_if + 0.4 * norm_rf
        if c < 0.25: return "LOW"
        if c < 0.50: return "MEDIUM"
        if c < 0.75: return "HIGH"
        return "CRITICAL"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _batch_vote(self, X_sc, X_rf, y, y_hat, residuals) -> np.ndarray:
        if_preds = (self.if_model.predict(X_sc) == -1).astype(float)
        rf_preds = (residuals > self.rf_threshold).astype(float)
        return (self.if_weight * if_preds + self.rf_weight * rf_preds >= 0.5).astype(int)

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, p)

    @classmethod
    def load(cls, path: str | Path) -> "EnsembleDetector":
        p = Path(path)
        if p.exists():
            return joblib.load(p)
        return cls()


# ── Standalone metric helper ───────────────────────────────────────────────────

def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall":    round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1":        round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "accuracy":  round(float(accuracy_score(y_true, y_pred)), 4),
    }
