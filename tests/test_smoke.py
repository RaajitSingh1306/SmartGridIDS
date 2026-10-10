import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.data_gen import load_dataset, random_record
from backend.detector import EnsembleDetector
from backend.config import settings
from backend import db


async def test_pipeline():
    print("1. Loading/generating data...")
    df, is_real = load_dataset(settings.data_path)
    print(f"   Data shape: {df.shape}, Real: {is_real}")

    print("2. Training EnsembleDetector...")
    det = EnsembleDetector(
        if_n_estimators=50,  # fast test
        rf_n_estimators=50,
    )
    metrics = det.train(df)
    print(f"   Metrics: {metrics}")

    print("3. Testing prediction & SHAP...")
    rec = random_record(anomaly=True)
    res = det.predict_one(rec)
    print(f"   Anomaly result: is_anomaly={res['is_anomaly']}, severity={res['severity']}, top_feature={res['top_feature']}")

    print("4. Testing save & load...")
    det.save(settings.model_path)
    loaded = EnsembleDetector.load(settings.model_path)
    print(f"   Loaded is_trained: {loaded.is_trained}")

    print("5. Testing Database...")
    await db.init_db()
    alert_id = await db.insert_alert(res, rec)
    count = await db.count_alerts()
    alerts = await db.get_alerts(limit=5)
    print(f"   Inserted alert id={alert_id}, count={count}, fetched={len(alerts)}")

    print("\n[SUCCESS] Pipeline and models validated!")


if __name__ == "__main__":
    asyncio.run(test_pipeline())
