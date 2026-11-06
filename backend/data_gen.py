"""
Loads the smart grid CSV if present; otherwise generates synthetic data
matching the paper's statistics (Table IV: means, std devs, anomaly rate 5%).
"""

import numpy as np
import pandas as pd
from pathlib import Path

FEATURES = [
    "Packet_Transmission_Rate_pps",
    "Data_Volume_KBps",
    "Requests_per_SM",
    "Network_Latency_ms",
]


def load_dataset(path: str) -> tuple[pd.DataFrame, bool]:
    """Returns (df, is_real). Falls back to synthetic if file missing."""
    p = Path(path)
    if p.exists():
        df = pd.read_csv(p)
        _validate(df)
        return df, True
    print(f"[data_gen] {path} not found — generating synthetic data")
    return generate_synthetic(), False


def generate_synthetic(n: int = 3000, anomaly_rate: float = 0.05, seed: int = 42) -> pd.DataFrame:
    """Generates smart grid traffic matching paper's Table IV statistics.

    Normal traffic:  low packet rate, moderate volume, low latency.
    Anomalous (DoS): high packet rate, high volume, high requests, high latency.
    """
    rng = np.random.default_rng(seed)
    n_anom = int(n * anomaly_rate)
    n_norm = n - n_anom

    # Normal — paper: pps≈110, vol≈549, req≈23, lat≈33
    norm = pd.DataFrame({
        "Packet_Transmission_Rate_pps": rng.normal(110, 30, n_norm).clip(67, 200),
        "Data_Volume_KBps":             rng.normal(549, 150, n_norm).clip(341, 900),
        "Requests_per_SM":              rng.normal(23, 8, n_norm).clip(8, 60),
        "Network_Latency_ms":           rng.normal(33, 10, n_norm).clip(10, 60),
        "Anomaly": 0,
    })

    # Anomalous — DoS signature: overwhelm all channels simultaneously
    anom = pd.DataFrame({
        "Packet_Transmission_Rate_pps": rng.normal(360, 25, n_anom).clip(280, 399),
        "Data_Volume_KBps":             rng.normal(1750, 80, n_anom).clip(1500, 1890),
        "Requests_per_SM":              rng.normal(92, 8, n_anom).clip(70, 104),
        "Network_Latency_ms":           rng.normal(135, 10, n_anom).clip(100, 152),
        "Anomaly": 1,
    })

    df = pd.concat([norm, anom], ignore_index=True)
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


def _validate(df: pd.DataFrame) -> None:
    required = set(FEATURES + ["Anomaly"])
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")


def random_record(anomaly: bool = False, seed: int | None = None) -> dict:
    """Generate a single realistic record for simulation / testing."""
    rng = np.random.default_rng(seed)
    if anomaly:
        return {
            "Packet_Transmission_Rate_pps": float(np.clip(rng.normal(360, 25), 280, 399)),
            "Data_Volume_KBps":             float(np.clip(rng.normal(1750, 80), 1500, 1890)),
            "Requests_per_SM":              float(np.clip(rng.normal(92, 8), 70, 104)),
            "Network_Latency_ms":           float(np.clip(rng.normal(135, 10), 100, 152)),
        }
    return {
        "Packet_Transmission_Rate_pps": float(np.clip(rng.normal(110, 30), 67, 200)),
        "Data_Volume_KBps":             float(np.clip(rng.normal(549, 150), 341, 900)),
        "Requests_per_SM":              float(np.clip(rng.normal(23, 8), 8, 60)),
        "Network_Latency_ms":           float(np.clip(rng.normal(33, 10), 10, 60)),
    }
