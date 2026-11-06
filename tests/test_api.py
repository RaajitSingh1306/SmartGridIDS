import sys
from pathlib import Path
import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.main import app

def test_api_workflow():
    with TestClient(app) as client:
        # 1. Health check before train
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        print(f"Health check: {data}")

        # 2. Train model
        print("Training model via API...")
        res = client.post("/train")
        assert res.status_code == 200
        train_data = res.json()
        assert train_data["status"] == "ok"
        print(f"Train response: {train_data['status']}, rows: {train_data['rows_used']}")

        # 3. Check metrics
        res = client.get("/metrics")
        assert res.status_code == 200
        metrics = res.json()
        assert metrics["is_trained"] is True
        print(f"Metrics: F1={metrics['f1']}, Acc={metrics['accuracy']}")

        # 4. Detect single normal record
        normal_record = {
            "Packet_Transmission_Rate_pps": 105.0,
            "Data_Volume_KBps": 520.0,
            "Requests_per_SM": 20.0,
            "Network_Latency_ms": 30.0,
        }
        res = client.post("/detect", json=normal_record)
        assert res.status_code == 200
        det_norm = res.json()
        print(f"Normal detect: is_anomaly={det_norm['is_anomaly']}, sev={det_norm['severity']}")

        # 5. Detect single anomaly record
        attack_record = {
            "Packet_Transmission_Rate_pps": 375.0,
            "Data_Volume_KBps": 1800.0,
            "Requests_per_SM": 95.0,
            "Network_Latency_ms": 140.0,
        }
        res = client.post("/detect", json=attack_record)
        assert res.status_code == 200
        det_att = res.json()
        assert det_att["is_anomaly"] is True
        print(f"Attack detect: is_anomaly={det_att['is_anomaly']}, sev={det_att['severity']}, top={det_att['top_feature']}")

        # 6. Detect batch
        res = client.post("/detect/batch", json=[normal_record, attack_record])
        assert res.status_code == 200
        batch_res = res.json()
        assert batch_res["total"] == 2
        assert batch_res["anomalies"] >= 1
        print(f"Batch detect: total={batch_res['total']}, anomalies={batch_res['anomalies']}")

        # 7. Check alerts
        res = client.get("/alerts")
        assert res.status_code == 200
        alerts = res.json()
        print(f"Alerts logged: {len(alerts)}")

        # 8. Check count
        res = client.get("/alerts/count")
        assert res.status_code == 200
        print(f"Alerts count: {res.json()['count']}")

        # 9. Clear alerts (DELETE)
        res = client.delete("/alerts/clear")
        assert res.status_code == 200
        print(f"Deleted alerts: {res.json()['deleted']}")

        # 10. Check count after clear
        res = client.get("/alerts/count")
        assert res.status_code == 200
        assert res.json()["count"] == 0

        print("\n[SUCCESS] All API endpoints validated successfully!")

if __name__ == "__main__":
    test_api_workflow()
