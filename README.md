# ⚡ Smart Grid IDS

Machine learning–based intrusion detection for flooding attacks in smart grid communication networks.  
Extends the ICICCD-2025 paper by shipping a production-ready ensemble with explainability, real-time alerting, and a full web dashboard.

---

## Paper → Project upgrades

| Dimension | Paper (ICICCD-2025) | This project |
|---|---|---|
| Model | IF and RF evaluated separately | Weighted ensemble: 0.6·IF + 0.4·RF |
| Explainability | None | SHAP feature attribution per alert |
| Severity | Binary anomaly/normal | LOW → MEDIUM → HIGH → CRITICAL |
| Deployment | Notebook | FastAPI + NiceGUI + Docker Compose |
| Persistence | None | SQLite alert log with timestamps |
| Data dependency | CSV required | Auto-generates synthetic data if CSV missing |
| Feature scaling | StandardScaler | RobustScaler (outlier-resistant) |
| Threshold | Fixed 95th percentile | Configurable via env, recalibrated on retrain |
| Alerting | Conceptual | Live dashboard, severity badges, top-feature column |

All upgrades are additive — no extra training cost, no new data requirements.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  NiceGUI  :8080                                 │
│  Dashboard · Simulation · Model controls        │
└────────────────────┬────────────────────────────┘
                     │ HTTP / REST
┌────────────────────▼────────────────────────────┐
│  FastAPI  :8000                                 │
│  /detect  /detect/batch  /train  /metrics       │
│  /alerts  /alerts/clear  /health  /ws/stream    │
└────────┬──────────────────────┬─────────────────┘
         │                      │
┌────────▼──────┐    ┌──────────▼──────────────┐
│ EnsembleModel │    │ SQLite  alerts.db        │
│  IsoForest    │    │  id · ts · severity      │
│  RF Regressor │    │  score · top_feature     │
│  SHAP         │    │  raw features            │
└───────────────┘    └─────────────────────────┘
```

---

## Quick start

### Local (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Terminal 1 — backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
python frontend/app.py
```

Open http://localhost:8080 → click **Train Model** → **Start Simulation**.

### Docker

```bash
make up          # builds + starts both services
make logs        # tail logs
make down        # stop
```

---

## API reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/detect` | Single record → anomaly result + SHAP |
| `POST` | `/detect/batch` | Array of records |
| `POST` | `/train` | (Re)train on dataset |
| `GET` | `/metrics` | Precision / recall / F1 / accuracy |
| `GET` | `/alerts` | Alert history (`?limit=N&severity=HIGH`) |
| `DELETE` | `/alerts/clear` | Wipe alert log |
| `GET` | `/health` | Model status |
| `WS` | `/ws/stream` | Push simulated detections |

### Detect payload

```json
{
  "Packet_Transmission_Rate_pps": 350.2,
  "Data_Volume_KBps": 1720.5,
  "Requests_per_SM": 88.3,
  "Network_Latency_ms": 128.7
}
```

### Detect response

```json
{
  "is_anomaly": true,
  "severity": "HIGH",
  "ensemble_score": 0.9,
  "if_score": -0.312,
  "rf_residual": 47.3,
  "top_feature": "Packet_Transmission_Rate_pps",
  "top_shap_value": 12.45
}
```

---

## Project structure

```
smart-grid-ids/
├── backend/
│   ├── main.py           # FastAPI app + lifespan
│   ├── config.py         # Settings via env
│   ├── db.py             # Async SQLite
│   ├── schemas.py        # Pydantic models
│   ├── detector.py       # EnsembleDetector
│   ├── data_gen.py       # CSV loader + synthetic generator
│   └── routers/
│       ├── detect.py
│       ├── metrics.py
│       ├── alerts.py
│       └── stream.py
├── frontend/
│   └── app.py            # NiceGUI dashboard
├── data/                 # Place flooding_smart_grid_dataset.csv here
├── models/saved/         # Persisted model artefacts
├── docker-compose.yml
├── requirements.txt
├── Makefile
├── SECURITY.md
└── .env.example
```

---

## Dataset

Place `flooding_smart_grid_dataset.csv` in `data/`. If absent, the system auto-generates 3,000-row synthetic data matching the paper's statistics (110 pps mean, 5% anomaly rate) so the project runs standalone.

Columns: `Packet_Transmission_Rate_pps`, `Data_Volume_KBps`, `Requests_per_SM`, `Network_Latency_ms`, `Anomaly`.

---

## Citation

> R. J. Singh, G. Sharma, J. Joshi, "Flooding Attack in Smart Grid," ICICCD-2025, NIIT University, Neemrana.
